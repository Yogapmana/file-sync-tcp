import argparse
import csv
import hashlib
import json
import socket
import ssl
import threading
from datetime import datetime
from pathlib import Path

from common import BUFFER_SIZE, ProtocolError, recv_exact, recv_json, safe_join, send_json, recv_compressed_chunk, send_compressed_chunk


STORAGE_DIR = Path("server_storage")
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "sync_log.csv"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_log_file() -> None:
    LOG_DIR.mkdir(exist_ok=True)

    if not LOG_FILE.exists():
        with LOG_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "waktu",
                "client_ip",
                "client_id",
                "file",
                "ukuran_byte",
                "status",
                "keterangan",
            ])


def write_log(client_ip: str, client_id: str, filename: str, size: int, status: str, note: str) -> None:
    ensure_log_file()

    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            now_text(),
            client_ip,
            client_id,
            filename,
            size,
            status,
            note,
        ])


def load_manifest(client_dir: Path) -> dict:
    manifest_path = client_dir / ".server_manifest.json"

    if not manifest_path.exists():
        return {}

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_manifest(client_dir: Path, manifest: dict) -> None:
    manifest_path = client_dir / ".server_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def receive_file(sock: socket.socket, target_path: Path, expected_size: int, received: int = 0) -> tuple[int, str]:
    """
    Menerima file dari client, menyimpan ke file temporary,
    lalu memindahkan ke target jika hash dan ukuran berhasil dihitung.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")

    sha256 = hashlib.sha256()

    if received > 0 and temp_path.exists():
        with temp_path.open("rb") as f:
            while True:
                chunk = f.read(BUFFER_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
    else:
        temp_path.unlink(missing_ok=True)
        received = 0

    with temp_path.open("ab") as f:
        while received < expected_size:
            chunk = recv_compressed_chunk(sock)
            if not chunk:
                break
            
            f.write(chunk)
            sha256.update(chunk)
            received += len(chunk)

    if received == expected_size:
            # Implementasi File Versioning sebelum menimpa file
            if target_path.exists():
                versions_dir = target_path.parent / "_versions"
                versions_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Pisahkan nama dan ekstensi
                name = target_path.stem
                ext = target_path.suffix
                backup_name = f"{name}_{timestamp}{ext}"
                backup_path = versions_dir / backup_name
                # Pindahkan file lama ke versi (hanya jika sukses didownload)
                try:
                    target_path.rename(backup_path)
                except Exception as e:
                    print(f"Gagal memindahkan {target_path.name} ke _versions: {e}")

            # Timpa dengan file yang baru diunduh
            temp_path.replace(target_path)
        
    return received, sha256.hexdigest()


def handle_upload(sock: socket.socket, client_ip: str, message: dict) -> None:
    client_id = message.get("client_id", "unknown_client")
    rel_path = message.get("rel_path")
    size = int(message.get("size", 0))
    expected_hash = message.get("sha256")

    if not rel_path or size < 0 or not expected_hash:
        send_json(sock, {"status": "ERROR", "message": "Metadata file tidak lengkap."})
        return

    client_dir = STORAGE_DIR / client_id
    client_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(client_dir)
    old_info = manifest.get(rel_path)

    target_path = safe_join(client_dir, rel_path)

    # Jika file sudah ada dengan hash yang sama, server tidak perlu menerima ulang.
    if target_path.exists() and old_info and old_info.get("sha256") == expected_hash:
        send_json(sock, {"status": "SKIP", "message": "File sudah ada dengan hash yang sama."})
        write_log(client_ip, client_id, rel_path, size, "SKIP", "File tidak berubah.")
        return

    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    received_size = temp_path.stat().st_size if temp_path.exists() else 0
    if received_size > size:
        temp_path.unlink()
        received_size = 0

    send_json(sock, {"status": "READY", "message": "Server siap menerima file.", "received_size": received_size})

    received_size, actual_hash = receive_file(sock, target_path, size, received_size)

    if received_size != size:
        send_json(sock, {"status": "ERROR", "message": "Ukuran file yang diterima tidak sesuai."})
        write_log(client_ip, client_id, rel_path, size, "FAILED", "Ukuran file tidak sesuai.")
        return

    if actual_hash != expected_hash:
        temp_path.unlink(missing_ok=True)
        send_json(sock, {"status": "ERROR", "message": "Hash file tidak sesuai. File ditolak."})
        write_log(client_ip, client_id, rel_path, size, "FAILED", "Hash file tidak sesuai.")
        return

    manifest[rel_path] = {
        "size": size,
        "sha256": actual_hash,
        "synced_at": now_text(),
    }
    save_manifest(client_dir, manifest)

    send_json(sock, {"status": "OK", "message": "File berhasil disinkronkan."})
    write_log(client_ip, client_id, rel_path, size, "SUCCESS", "File berhasil diterima.")


def handle_client(sock: socket.socket, address: tuple[str, int]) -> None:
    client_ip, client_port = address
    print(f"[{now_text()}] Client terhubung: {client_ip}:{client_port}")

    with sock:
        try:
            while True:
                message = recv_json(sock)
                action = message.get("action")
                client_id = message.get("client_id", "unknown_client")

                if action == "GET_MANIFEST":
                    client_dir = STORAGE_DIR / client_id
                    manifest = load_manifest(client_dir)
                    send_json(sock, {"status": "SUCCESS", "manifest": manifest})

                elif action == "UPLOAD":
                    handle_upload(sock, client_ip, message)

                elif action == "DELETE":
                    rel_path = message.get("rel_path")
                    if rel_path:
                        client_dir = STORAGE_DIR / client_id
                        target_path = safe_join(client_dir, rel_path)
                        
                        if target_path.exists():
                            # Memindahkan file ke folder _versions saat dihapus
                            versions_dir = target_path.parent / "_versions"
                            versions_dir.mkdir(exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            name = target_path.stem
                            ext = target_path.suffix
                            backup_name = f"{name}_deleted_{timestamp}{ext}"
                            backup_path = versions_dir / backup_name
                            
                            try:
                                target_path.rename(backup_path)
                                write_log(client_ip, client_id, rel_path, 0, "SUCCESS", "File dihapus oleh client (pindah ke _versions)")
                            except Exception as e:
                                print(f"Gagal memindahkan file ke _versions: {e}")
                                write_log(client_ip, client_id, rel_path, 0, "FAILED", f"Gagal menghapus: {str(e)}")
                        
                        manifest = load_manifest(client_dir)
                        if rel_path in manifest:
                            del manifest[rel_path]
                            save_manifest(client_dir, manifest)
                            
                    send_json(sock, {"status": "OK", "message": "Penghapusan diproses."})

                elif action == "LIST_VERSIONS":
                    client_dir = STORAGE_DIR / client_id
                    versions_dir = client_dir / "_versions"
                    versions_list = []
                    
                    if versions_dir.exists():
                        for f in versions_dir.iterdir():
                            if f.is_file():
                                mtime_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                                versions_list.append({
                                    "filename": f.name,
                                    "size": f.stat().st_size,
                                    "mtime": mtime_str
                                })
                                
                    versions_list.sort(key=lambda x: x["mtime"], reverse=True)
                                
                    send_json(sock, {"status": "SUCCESS", "versions": versions_list})

                elif action == "RESTORE":
                    filename = message.get("filename")
                    if not filename:
                        continue
                        
                    client_dir = STORAGE_DIR / client_id
                    versions_dir = client_dir / "_versions"
                    target_file = versions_dir / filename
                    
                    if not target_file.exists():
                        send_json(sock, {"status": "FAILED", "reason": "File not found"})
                        continue
                        
                    file_size = target_file.stat().st_size
                    send_json(sock, {"status": "SUCCESS", "filesize": file_size})
                    
                    with target_file.open("rb") as f:
                        while True:
                            chunk = f.read(BUFFER_SIZE)
                            if not chunk:
                                break
                            send_compressed_chunk(sock, chunk)
                    send_compressed_chunk(sock, b"")

                elif action == "DOWNLOAD":
                    rel_path = message.get("rel_path")
                    if not rel_path:
                        continue
                        
                    client_dir = STORAGE_DIR / client_id
                    target_file = safe_join(client_dir, rel_path)
                    
                    if not target_file.exists() or not target_file.is_file():
                        send_json(sock, {"status": "FAILED", "reason": "File not found"})
                        continue
                        
                    file_size = target_file.stat().st_size
                    send_json(sock, {"status": "SUCCESS", "filesize": file_size})
                    
                    with target_file.open("rb") as f:
                        while True:
                            chunk = f.read(BUFFER_SIZE)
                            if not chunk:
                                break
                            send_compressed_chunk(sock, chunk)
                    send_compressed_chunk(sock, b"")

                elif action == "FINISH":
                    send_json(sock, {"status": "OK", "message": "Sinkronisasi selesai."})
                    print(f"[{now_text()}] Sinkronisasi selesai dari {client_ip}:{client_port}")
                    break

                else:
                    send_json(sock, {"status": "ERROR", "message": "Action tidak dikenali."})

        except (ConnectionError, ProtocolError) as exc:
            print(f"[{now_text()}] Koneksi bermasalah dari {client_ip}:{client_port}: {exc}")
        except Exception as exc:
            print(f"[{now_text()}] Error dari {client_ip}:{client_port}: {exc}")


def start_server(host: str, port: int) -> None:
    STORAGE_DIR.mkdir(exist_ok=True)
    ensure_log_file()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Agar port bisa langsung dipakai lagi setelah server dimatikan.
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((host, port))
    server_socket.listen(10)

    # Menyiapkan SSL Context jika sertifikat tersedia
    cert_file = Path("server.crt")
    key_file = Path("server.key")
    use_ssl = cert_file.exists() and key_file.exists()
    
    ssl_context = None
    if use_ssl:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        
    print("=" * 60)
    print("SERVER SINKRONISASI FILE TCP (SSL/TLS SECURED)")
    print(f"Listening di {host}:{port}")
    if use_ssl:
        print("🔐 Keamanan SSL/TLS Aktif")
    else:
        print("⚠️ SSL/TLS Non-aktif (sertifikat tidak ditemukan)")
    print(f"Folder storage: {STORAGE_DIR.resolve()}")
    print(f"File log: {LOG_FILE.resolve()}")
    print("=" * 60)

    try:
        while True:
            client_socket, address = server_socket.accept()
            
            # Bungkus dengan SSL jika aktif
            if ssl_context:
                try:
                    client_socket = ssl_context.wrap_socket(client_socket, server_side=True)
                except ssl.SSLError as e:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SSL Error dari {address}: {e}")
                    client_socket.close()
                    continue
            
            thread = threading.Thread(target=handle_client, args=(client_socket, address), daemon=True)
            thread.start()

    except KeyboardInterrupt:
        print("\nServer dihentikan.")
    finally:
        server_socket.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Server sinkronisasi file menggunakan TCP Socket.")
    parser.add_argument("--host", default="0.0.0.0", help="Host server. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=5001, help="Port server. Default: 5001")
    args = parser.parse_args()

    start_server(args.host, args.port)


if __name__ == "__main__":
    main()