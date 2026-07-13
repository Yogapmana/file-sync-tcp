import argparse
import hashlib
import json
import os
import socket
import time
from pathlib import Path

from common import BUFFER_SIZE, recv_json, send_json, send_compressed_chunk


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
            
        while True:
            chunk = f.read(BUFFER_SIZE)
            if not chunk:
                break

            send_compressed_chunk(sock, chunk)
            sent += len(chunk)
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

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((server_host, server_port))
        
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Client sinkronisasi file menggunakan TCP Socket.")
    parser.add_argument("--server", default="127.0.0.1", help="Alamat IP server. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=5001, help="Port server. Default: 5001")
    parser.add_argument("--folder", default="client_files", help="Folder yang akan disinkronkan. Default: client_files")
    parser.add_argument("--client-id", default=os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "client01")
    parser.add_argument("--force", action="store_true", help="Kirim semua file walaupun tidak berubah.")
    parser.add_argument("--watch", action="store_true", help="Auto sync dengan cara memonitor folder")
    parser.add_argument("--interval", type=int, default=2, help="Interval auto sync dalam detik (default: 2)")
    args = parser.parse_args()

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