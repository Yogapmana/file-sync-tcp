import argparse
import hashlib
import json
import os
import socket
import ssl
import time
import re
from pathlib import Path

from common import BUFFER_SIZE, ProtocolError, recv_json, send_json, send_compressed_chunk, recv_compressed_chunk


STATE_FILE = ".sync_state.json"


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def sha256_file(path: Path) -> str:
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(BUFFER_SIZE)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()


def load_state(folder: Path) -> dict:
    state_path = folder / STATE_FILE

    if not state_path.exists():
        return {}

    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(folder: Path, state: dict) -> None:
    state_path = folder / STATE_FILE
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def scan_folder(folder: Path) -> dict:
    """
    Membaca semua file di folder client, lalu membuat manifest.
    Manifest berisi path relatif, ukuran, waktu modifikasi, dan hash.
    """
    manifest = {}

    for path in folder.rglob("*"):
        if not path.is_file():
            continue

        if path.name == STATE_FILE:
            continue

        rel_path = path.relative_to(folder).as_posix()
        stat = path.stat()

        manifest[rel_path] = {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "sha256": sha256_file(path),
        }

    return manifest


def get_changed_files(current_manifest: dict, previous_state: dict, force: bool = False) -> dict:
    changed = {"upload": [], "delete": []}

    for rel_path, info in current_manifest.items():
        old_info = previous_state.get(rel_path)

        if force:
            changed["upload"].append(rel_path)
        elif old_info is None:
            changed["upload"].append(rel_path)
        elif old_info.get("sha256") != info.get("sha256"):
            changed["upload"].append(rel_path)
            
    for rel_path in previous_state.keys():
        if rel_path not in current_manifest:
            changed["delete"].append(rel_path)

    return changed


def print_progress(filename: str, sent: int, total: int) -> None:
    if total == 0:
        percent = 100
    else:
        percent = int((sent / total) * 100)

    bar_length = 30
    filled = int(bar_length * percent / 100)
    bar = "#" * filled + "-" * (bar_length - filled)

    print(f"\rMengirim {filename} [{bar}] {percent}% ({format_size(sent)}/{format_size(total)})", end="")


def send_file(sock: socket.socket, folder: Path, client_id: str, rel_path: str, info: dict) -> str:
    full_path = folder / rel_path
    size = info["size"]

    metadata = {
        "action": "UPLOAD",
        "client_id": client_id,
        "rel_path": rel_path,
        "size": size,
        "sha256": info["sha256"],
        "mtime": info["mtime"],
    }

    send_json(sock, metadata)
    response = recv_json(sock)

    if response.get("status") == "SKIP":
        print(f"[SKIP] {rel_path} - {response.get('message')}")
        return "SKIP"

    if response.get("status") != "READY":
        print(f"[GAGAL] {rel_path} - {response.get('message')}")
        return "FAILED"

    received_size = response.get("received_size", 0)
    sent = received_size
    start_time = time.time()

    with full_path.open("rb") as f:
        if received_size > 0:
            f.seek(received_size)
            print(f"[RESUME] Melanjutkan {rel_path} dari {format_size(received_size)}")
            
        remaining = size - received_size
        while remaining > 0:
            chunk_size = min(BUFFER_SIZE, remaining)
            chunk = f.read(chunk_size)
            if not chunk:
                break

            send_compressed_chunk(sock, chunk)
            sent += len(chunk)
            remaining -= len(chunk)
            print_progress(rel_path, sent, size)

    print()

    final_response = recv_json(sock)
    elapsed = max(time.time() - start_time, 0.0001)
    speed = sent / elapsed

    if final_response.get("status") == "OK":
        print(f"[OK] {rel_path} berhasil dikirim. Kecepatan: {format_size(int(speed))}/s")
        return "OK"

    print(f"[GAGAL] {rel_path} - {final_response.get('message')}")
    return "FAILED"


def sync_folder(server_host: str, server_port: int, folder: Path, client_id: str, force: bool = False, watch_mode: bool = False) -> None:
    if not folder.exists():
        raise FileNotFoundError(f"Folder tidak ditemukan: {folder}")

    if not folder.is_dir():
        raise NotADirectoryError(f"Path bukan folder: {folder}")

    previous_state = load_state(folder)
    current_manifest = scan_folder(folder)
    changed_files = get_changed_files(current_manifest, previous_state, force=force)

    total_changes = len(changed_files["upload"]) + len(changed_files["delete"])

    if watch_mode and total_changes == 0:
        return

    print("=" * 60)
    print("CLIENT SINKRONISASI FILE TCP")
    print(f"Server: {server_host}:{server_port}")
    print(f"Folder client: {folder.resolve()}")
    print(f"Client ID: {client_id}")
    print("=" * 60)

    print(f"Total file di folder: {len(current_manifest)}")
    print(f"File diupload: {len(changed_files['upload'])}")
    print(f"File dihapus: {len(changed_files['delete'])}")

    if total_changes == 0:
        print("Tidak ada file baru, diubah, atau dihapus. Sinkronisasi tidak diperlukan.")
        return

    success_count = 0
    skip_count = 0
    failed_count = 0
    delete_count = 0

    sock = connect_to_server(server_host, server_port)
    if not sock:
        print("Sinkronisasi dibatalkan karena gagal terhubung ke server.")
        return
        
    with sock:
        
        for rel_path in changed_files["delete"]:
            send_json(sock, {"action": "DELETE", "client_id": client_id, "rel_path": rel_path})
            resp = recv_json(sock)
            if resp.get("status") == "OK":
                print(f"[DELETE] {rel_path} berhasil dihapus dari server.")
                delete_count += 1
            else:
                print(f"[GAGAL] Gagal menghapus {rel_path}: {resp.get('message')}")

        for rel_path in changed_files["upload"]:
            result = send_file(sock, folder, client_id, rel_path, current_manifest[rel_path])

            if result == "OK":
                success_count += 1
            elif result == "SKIP":
                skip_count += 1
            else:
                failed_count += 1

        send_json(sock, {"action": "FINISH", "client_id": client_id})
        finish_response = recv_json(sock)
        print(f"Server: {finish_response.get('message')}")

    # State tetap disimpan supaya file yang tidak berubah tidak dikirim ulang.
    save_state(folder, current_manifest)

    print("=" * 60)
    print("RINGKASAN SINKRONISASI")
    print(f"Diunggah: {success_count}")
    print(f"Dihapus : {delete_count}")
    print(f"Dilewati: {skip_count}")
    print(f"Gagal   : {failed_count}")
    print("=" * 60)


def connect_to_server(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        # Amankan dengan SSL/TLS (menggunakan CERT_NONE karena self-signed certificate)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        secure_sock = context.wrap_socket(sock, server_hostname=host)
        return secure_sock
    except ssl.SSLError as e:
        print(f"SSL Error: {e}\nPastikan server.py telah dinyalakan dengan SSL/TLS yang aktif.")
        return None
    except Exception as e:
        print(f"Gagal terhubung ke server: {e}")
        return None


def fetch_versions(server_host: str, server_port: int, client_id: str) -> list:
    """Mengambil daftar versi file dari server."""
    sock = connect_to_server(server_host, server_port)
    if not sock:
        return []
    try:
        send_json(sock, {"action": "LIST_VERSIONS", "client_id": client_id})
        response = recv_json(sock)
        if response.get("status") == "SUCCESS":
            return response.get("versions", [])
        return []
    except Exception as e:
        print(f"Error fetch versions: {e}")
        return []
    finally:
        sock.close()


def restore_file(server_host: str, server_port: int, client_id: str, filename: str, client_dir: Path) -> bool:
    """Melakukan restore file tunggal dari server."""
    sock = connect_to_server(server_host, server_port)
    if not sock:
        return False
    try:
        send_json(sock, {"action": "RESTORE", "client_id": client_id, "filename": filename})
        response = recv_json(sock)
        
        if response.get("status") == "SUCCESS":
            original_name = re.sub(r'_\d{8}_\d{6}', '', filename)
            original_name = re.sub(r'_deleted', '', original_name)
            target_path = client_dir / original_name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with target_path.open("wb") as f:
                while True:
                    chunk = recv_compressed_chunk(sock)
                    if not chunk:
                        break
                    f.write(chunk)
            
            manifest = load_state(client_dir)
            manifest[original_name] = {
                "size": target_path.stat().st_size,
                "mtime": target_path.stat().st_mtime,
                "sha256": sha256_file(target_path)
            }
            save_state(client_dir, manifest)
            return True
        else:
            print(f"Gagal restore: {response.get('reason')}")
            return False
    except Exception as e:
        print(f"Error saat restore: {e}")
        return False
    finally:
        sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Client sinkronisasi file menggunakan TCP Socket.")
    parser.add_argument("--server", default="127.0.0.1", help="Alamat IP server. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=5001, help="Port server. Default: 5001")
    parser.add_argument("--folder", default="client_files", help="Folder yang akan disinkronkan. Default: client_files")
    parser.add_argument("--client-id", default=os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "client01")
    parser.add_argument("--force", action="store_true", help="Kirim semua file walaupun tidak berubah.")
    parser.add_argument("--watch", action="store_true", help="Pantau folder secara terus menerus (auto-sync)")
    parser.add_argument("--interval", type=int, default=2, help="Interval (detik) untuk mode watch")
    parser.add_argument("--list-versions", action="store_true", help="Lihat daftar versi/backup file lama di server")
    parser.add_argument("--restore", type=str, metavar="NAMA_FILE", help="Restore file dari versi sebelumnya yang ada di server")
    args = parser.parse_args()

    client_dir = Path(args.folder)
    if not client_dir.exists() and not args.list_versions and not args.restore:
        client_dir.mkdir(parents=True)
        print(f"Folder '{args.folder}' dibuat.")

    if args.list_versions:
        versions = fetch_versions(args.server, args.port, args.client_id)
        print("\n=== DAFTAR FILE BACKUP / VERSI LAMA DI SERVER ===")
        if not versions:
            print("Belum ada file backup.")
        for v in versions:
            size_kb = v['size'] / 1024
            print(f"- {v['filename']}  ({size_kb:.1f} KB, {v['mtime']})")
        print("=================================================")
        print("Ketik: python client.py --restore <nama_file> untuk mengembalikan file.")
        return

    if args.restore:
        success = restore_file(args.server, args.port, args.client_id, args.restore, client_dir)
        if success:
            print(f"✅ Berhasil di-restore.")
        else:
            print("❌ Gagal me-restore file.")
        return

    if args.watch:
        print(f"Memulai auto-sync setiap {args.interval} detik. Tekan Ctrl+C untuk berhenti.")
        try:
            while True:
                sync_folder(
                    server_host=args.server,
                    server_port=args.port,
                    folder=Path(args.folder),
                    client_id=args.client_id,
                    force=args.force,
                    watch_mode=True
                )
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nAuto-sync dihentikan.")
    else:
        sync_folder(
            server_host=args.server,
            server_port=args.port,
            folder=Path(args.folder),
            client_id=args.client_id,
            force=args.force,
        )


if __name__ == "__main__":
    main()