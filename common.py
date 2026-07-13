import json
import struct
import socket
import zlib
from pathlib import Path

BUFFER_SIZE = 64 * 1024


class ProtocolError(Exception):
    """Error untuk format data socket yang tidak valid."""


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """
    Membaca data dari socket sebanyak n byte.
    Fungsi ini dibutuhkan karena recv() tidak selalu langsung mengembalikan semua byte.
    """
    data = bytearray()

    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Koneksi terputus saat menerima data.")
        data.extend(packet)

    return bytes(data)


def send_json(sock: socket.socket, payload: dict) -> None:
    """
    Mengirim JSON dengan format:
    4 byte panjang JSON + isi JSON.
    """
    raw = json.dumps(payload).encode("utf-8")
    sock.sendall(struct.pack("!I", len(raw)))
    sock.sendall(raw)


def recv_json(sock: socket.socket) -> dict:
    """
    Menerima JSON dengan format:
    4 byte panjang JSON + isi JSON.
    """
    header = recv_exact(sock, 4)
    length = struct.unpack("!I", header)[0]

    if length <= 0 or length > 10_000_000:
        raise ProtocolError("Panjang JSON tidak valid.")

    raw = recv_exact(sock, length)

    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ProtocolError("JSON tidak valid.") from exc


def safe_join(base_dir: Path, relative_path: str) -> Path:
    """
    Menggabungkan base_dir dan relative_path secara aman.
    Tujuannya supaya client tidak bisa mengirim path seperti ../../file_rahasia.
    """
    base_dir = base_dir.resolve()
    target = (base_dir / relative_path).resolve()

    if base_dir != target and base_dir not in target.parents:
        raise ProtocolError("Path file tidak aman.")

    return target


def send_compressed_chunk(sock: socket.socket, chunk: bytes) -> None:
    comp = zlib.compress(chunk)
    sock.sendall(struct.pack("!I", len(comp)))
    sock.sendall(comp)


def recv_compressed_chunk(sock: socket.socket) -> bytes:
    header = recv_exact(sock, 4)
    length = struct.unpack("!I", header)[0]
    
    if length <= 0 or length > 10_000_000:
        raise ProtocolError("Panjang compressed chunk tidak valid.")
        
    comp = recv_exact(sock, length)
    return zlib.decompress(comp)