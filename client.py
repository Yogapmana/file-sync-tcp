import argparse
import fnmatch
import hashlib
import json
import logging
import os
import re
import socket
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)

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
    
    ignore_patterns = []
    syncignore_path = folder / ".syncignore"
    if syncignore_path.exists():
        with open(syncignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ignore_patterns.append(line)

    for path in folder.rglob("*"):
        if not path.is_file():
            continue

        if path.name == STATE_FILE or path.name == ".syncignore":
            continue

        rel_path = path.relative_to(folder).as_posix()
        
        is_ignored = False
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(path.name, pattern):
                is_ignored = True
                break
                
        if is_ignored:
            continue

        rel_path = path.relative_to(folder).as_posix()
        stat = path.stat()

        manifest[rel_path] = {
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "sha256": sha256_file(path),
        }

    return manifest


def get_changed_files(current_manifest: dict, previous_state: dict, server_manifest: dict, force: bool = False) -> tuple[dict, list]:
    changed = {"upload": [], "download": [], "delete_remote": [], "delete_local": [], "conflict": []}
    cooldown_files = []

    now = time.time()
    COOLDOWN_SECONDS = 5
    
    all_files = set(current_manifest.keys()) | set(previous_state.keys()) | set(server_manifest.keys())
    
    for rel_path in all_files:
        local_info = current_manifest.get(rel_path)
        prev_info = previous_state.get(rel_path)
        server_info = server_manifest.get(rel_path)
        
        local_hash = local_info.get("sha256") if local_info else None
        prev_hash = prev_info.get("sha256") if prev_info else None
        server_hash = server_info.get("sha256") if server_info else None
        
        modified_locally = False
        if local_info:
            if not prev_info or local_hash != prev_hash:
                modified_locally = True
                
        modified_server = False
        if server_info:
            if not prev_info or server_hash != prev_hash:
                modified_server = True
                
        deleted_locally = (prev_info is not None) and (local_info is None)
        deleted_server = (prev_info is not None) and (server_info is None)
        
        if force and local_info:
            changed["upload"].append(rel_path)
            continue
            
        if modified_locally and modified_server:
            if local_hash == server_hash:
                continue
            changed["conflict"].append(rel_path)
            
        elif modified_locally and deleted_server:
            if (now - local_info["mtime"]) < COOLDOWN_SECONDS:
                logging.info(f"[COOLDOWN] Menunda sinkronisasi '{rel_path}' karena masih diedit...")
                cooldown_files.append(rel_path)
            else:
                changed["upload"].append(rel_path)
                
        elif deleted_locally and modified_server:
            changed["download"].append(rel_path)
            
        elif modified_locally:
            if (now - local_info["mtime"]) < COOLDOWN_SECONDS:
                logging.info(f"[COOLDOWN] Menunda sinkronisasi '{rel_path}' karena masih diedit...")
                cooldown_files.append(rel_path)
            else:
                changed["upload"].append(rel_path)
                
        elif modified_server:
            changed["download"].append(rel_path)
            
        elif deleted_locally:
            changed["delete_remote"].append(rel_path)
                
        elif deleted_server:
            changed["delete_local"].append(rel_path)

    return changed, cooldown_files


def print_progress(filename: str, sent: int, total: int) -> None:
    if total == 0:
        percent = 100
    else:
        percent = int((sent / total) * 100)

    bar_length = 30
    filled = int(bar_length * percent / 100)
    bar = "#" * filled + "-" * (bar_length - filled)

    print(f"\rMengirim {filename} [{bar}] {percent}% ({format_size(sent)}/{format_size(total)})", end="")


def download_file(sock: socket.socket, folder: Path, client_id: str, rel_path: str) -> str:
    metadata = {
        "action": "DOWNLOAD",
        "client_id": client_id,
        "rel_path": rel_path
    }
    send_json(sock, metadata)
    response = recv_json(sock)
    
    if response.get("status") != "SUCCESS":
        logging.error(f"[GAGAL] Download {rel_path} - {response.get('reason')}")
        return "FAILED"
        
    size = response.get("filesize", 0)
    full_path = folder / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    received = 0
    start_time = time.time()
    tmp_path = full_path.with_suffix(full_path.suffix + ".tmp_dl")
    
    with tmp_path.open("wb") as f:
        while received < size:
            chunk = recv_compressed_chunk(sock)
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)
            print_progress(rel_path, received, size)
            
    logging.info("")
    if received == size:
        tmp_path.replace(full_path)
        elapsed = max(time.time() - start_time, 0.0001)
        speed = received / elapsed
        logging.info(f"[OK] {rel_path} berhasil diunduh. Kecepatan: {format_size(int(speed))}/s")
        return "OK"
    else:
        tmp_path.unlink(missing_ok=True)
        logging.error(f"[GAGAL] {rel_path} ukuran tidak sesuai (Diterima: {received}/{size})")
        return "FAILED"

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
        logging.info(f"[SKIP] {rel_path} - {response.get('message')}")
        return "SKIP"

    if response.get("status") != "READY":
        logging.error(f"[GAGAL] {rel_path} - {response.get('message')}")
        return "FAILED"

    received_size = response.get("received_size", 0)
    sent = received_size
    start_time = time.time()

    with full_path.open("rb") as f:
        if received_size > 0:
            f.seek(received_size)
            logging.info(f"[RESUME] Melanjutkan {rel_path} dari {format_size(received_size)}")
            
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

    logging.info("")

    final_response = recv_json(sock)
    elapsed = max(time.time() - start_time, 0.0001)
    speed = sent / elapsed

    if final_response.get("status") == "OK":
        logging.info(f"[OK] {rel_path} berhasil dikirim. Kecepatan: {format_size(int(speed))}/s")
        return "OK"

    logging.error(f"[GAGAL] {rel_path} - {final_response.get('message')}")
    return "FAILED"


def sync_folder(server_host: str, server_port: int, folder: Path, client_id: str, force: bool = False, watch_mode: bool = False) -> None:
    if not folder.exists():
        raise FileNotFoundError(f"Folder tidak ditemukan: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Path bukan folder: {folder}")

    sock = connect_to_server(server_host, server_port)
    if not sock:
        logging.info("Sinkronisasi dibatalkan karena gagal terhubung ke server.")
        return

    with sock:
        send_json(sock, {"action": "GET_MANIFEST", "client_id": client_id})
        resp = recv_json(sock)
        if resp.get("status") == "SUCCESS":
            server_manifest = resp.get("manifest", {})
        else:
            logging.info("Gagal mengambil manifest dari server.")
            server_manifest = {}
            
        previous_state = load_state(folder)
        current_manifest = scan_folder(folder)
        
        changed_files, cooldown_files = get_changed_files(current_manifest, previous_state, server_manifest, force=force)

        # Tangani file conflict
        for rel_path in changed_files["conflict"]:
            full_path = folder / rel_path
            if full_path.exists():
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                conflict_name = f"{full_path.stem}_conflict_{timestamp}{full_path.suffix}"
                conflict_path = full_path.with_name(conflict_name)
                full_path.rename(conflict_path)
                logging.warning(f"[CONFLICT] Menyimpan file lokal ke {conflict_name}")
            changed_files["download"].append(rel_path)

        total_changes = len(changed_files["upload"]) + len(changed_files["delete_remote"]) + len(changed_files["download"]) + len(changed_files["delete_local"])
        if watch_mode and total_changes == 0:
            send_json(sock, {"action": "FINISH", "client_id": client_id})
            recv_json(sock)
            return

        logging.info("=" * 60)
        logging.info("CLIENT SINKRONISASI FILE TCP (TWO-WAY SYNC)")
        logging.info(f"Server: {server_host}:{server_port}")
        logging.info(f"Folder client: {folder.resolve()}")
        logging.info(f"Client ID: {client_id}")
        logging.info("=" * 60)
        
        if total_changes == 0:
            logging.info("Tidak ada file baru, diubah, atau dihapus. Sinkronisasi tidak diperlukan.")
            send_json(sock, {"action": "FINISH", "client_id": client_id})
            recv_json(sock)
            return

        success_count = 0
        skip_count = 0
        failed_count = 0
        delete_remote_count = 0
        delete_local_count = 0
        download_count = 0
        
        # Eksekusi Delete Lokal
        for rel_path in changed_files["delete_local"]:
            full_path = folder / rel_path
            if full_path.exists():
                full_path.unlink()
                logging.info(f"[DELETE LOKAL] {rel_path} berhasil dihapus.")
                delete_local_count += 1
                
        # Eksekusi Delete Remote
        for rel_path in changed_files["delete_remote"]:
            send_json(sock, {"action": "DELETE", "client_id": client_id, "rel_path": rel_path})
            r = recv_json(sock)
            if r.get("status") == "OK":
                logging.info(f"[DELETE REMOTE] {rel_path} berhasil dihapus dari server.")
                delete_remote_count += 1
            else:
                logging.error(f"[GAGAL] Menghapus remote {rel_path}: {r.get('message')}")
                
        # Eksekusi Upload
        for rel_path in changed_files["upload"]:
            result = send_file(sock, folder, client_id, rel_path, current_manifest[rel_path])
            if result == "OK":
                success_count += 1
            elif result == "SKIP":
                skip_count += 1
            else:
                failed_count += 1
                
        # Eksekusi Download
        for rel_path in changed_files["download"]:
            result = download_file(sock, folder, client_id, rel_path)
            if result == "OK":
                download_count += 1
            else:
                failed_count += 1

        send_json(sock, {"action": "FINISH", "client_id": client_id})
        finish_response = recv_json(sock)
        logging.info(f"Server: {finish_response.get('message')}")

    # Update State
    final_manifest = scan_folder(folder)
    for f in cooldown_files:
        if f in previous_state:
            final_manifest[f] = previous_state[f]
            
    save_state(folder, final_manifest)

    logging.info("=" * 60)
    logging.info("RINGKASAN SINKRONISASI")
    logging.info(f"Diunggah      : {success_count}")
    logging.info(f"Diunduh       : {download_count}")
    logging.info(f"Dihapus Lokal : {delete_local_count}")
    logging.info(f"Dihapus Server: {delete_remote_count}")
    logging.info(f"Dilewati      : {skip_count}")
    logging.info(f"Gagal         : {failed_count}")
    logging.info("=" * 60)

    logging.info(f"Total file lokal : {len(final_manifest)}")
    logging.info(f"File diupload    : {len(changed_files['upload'])}")
    logging.info(f"File dihapus     : {len(changed_files['delete_local']) + len(changed_files['delete_remote'])}")
def connect_to_server(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        # Amankan dengan SSL/TLS
        context = ssl.create_default_context()
        context.check_hostname = False
        # Memuat sertifikat server untuk validasi (Best Practice)
        if Path("server.crt").exists():
            context.load_verify_locations("server.crt")
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context.verify_mode = ssl.CERT_NONE
        
        secure_sock = context.wrap_socket(sock, server_hostname=host)
        
        # Auto-download sertifikat jika belum ada (Trust on First Use)
        if not Path("server.crt").exists():
            der_cert = secure_sock.getpeercert(binary_form=True)
            if der_cert:
                pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
                with open("server.crt", "w", encoding="utf-8") as f:
                    f.write(pem_cert)
                logging.info("Sertifikat server (server.crt) berhasil diunduh dan disimpan (Trust on First Use).")
                
        return secure_sock
    except ssl.SSLError as e:
        logging.error(f"SSL Error: {e}\nPastikan server.py telah dinyalakan dengan SSL/TLS yang aktif, dan server.crt valid.")
        return None
    except ConnectionRefusedError as e:
        logging.error(f"Koneksi ditolak oleh server: {e}")
        return None
    except OSError as e:
        logging.error(f"Gagal terhubung ke server: {e}")
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
        logging.error(f"Error fetch versions: {e}")
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
            
            return True
        else:
            logging.info(f"Gagal restore: {response.get('reason')}")
            return False
    except Exception as e:
        logging.error(f"Error saat restore: {e}")
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
        logging.info(f"Folder '{args.folder}' dibuat.")

    if args.list_versions:
        versions = fetch_versions(args.server, args.port, args.client_id)
        logging.info("\n=== DAFTAR FILE BACKUP / VERSI LAMA DI SERVER ===")
        if not versions:
            logging.info("Belum ada file backup.")
        for v in versions:
            size_kb = v['size'] / 1024
            logging.info(f"- {v['filename']}  ({size_kb:.1f} KB, {v['mtime']})")
        logging.info("=================================================")
        logging.info("Ketik: python client.py --restore <nama_file> untuk mengembalikan file.")
        return

    if args.restore:
        success = restore_file(args.server, args.port, args.client_id, args.restore, client_dir)
        if success:
            logging.info(f"✅ Berhasil di-restore.")
        else:
            logging.info("❌ Gagal me-restore file.")
        return

    if args.watch:
        logging.info(f"Memulai auto-sync setiap {args.interval} detik. Tekan Ctrl+C untuk berhenti.")
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
            logging.info("\nAuto-sync dihentikan.")
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