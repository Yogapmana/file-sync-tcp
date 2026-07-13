# Sistem Sinkronisasi File Client-Server Menggunakan TCP Socket

Project ini adalah aplikasi sederhana untuk menyinkronkan file dari folder client ke folder server melalui jaringan menggunakan TCP Socket.

## Fitur Utama

1. Client membaca isi folder lokal.
2. Client mendeteksi file baru atau file yang berubah.
3. File dikirim ke server menggunakan TCP.
4. Server menerima dan menyimpan file hasil sinkronisasi.
5. Server mencatat log sinkronisasi berisi:
   - waktu sinkronisasi
   - IP client
   - client_id
   - nama file
   - ukuran file
   - status sinkronisasi
   - keterangan
6. Client menampilkan status berhasil, gagal, atau file dilewati.
7. Server mendukung banyak client menggunakan threading.
8. File disimpan di folder server berdasarkan client_id.

## Materi yang Digunakan

- TCP Socket
- Client-Server
- Socket Programming
- Resource Sharing
- Network Operating System
- Logging aktivitas jaringan

## Struktur Folder

```text
file-sync-tcp-project/
├── client.py
├── server.py
├── common.py
├── requirements.txt
├── README.md
├── PENJELASAN_PROJECT.md
├── client_files/
│   └── contoh.txt
├── server_storage/
└── logs/
```

## Cara Menjalankan

### 1. Jalankan Server

Buka terminal pertama:

```bash
python server.py
```

Default server berjalan di:

```text
0.0.0.0:5001
```

### 2. Jalankan Client

Buka terminal kedua:

```bash
python client.py --server 127.0.0.1 --folder client_files --client-id client01
```

Jika menggunakan dua laptop dalam satu Wi-Fi/LAN, ganti `127.0.0.1` dengan IP laptop yang menjalankan server.

Contoh:

```bash
python client.py --server 192.168.1.10 --folder client_files --client-id laptop_rafie
```

## Cara Demo untuk Presentasi

1. Jalankan `server.py`.
2. Jalankan `client.py`.
3. File dari `client_files` akan masuk ke `server_storage/client01`.
4. Tambahkan file baru ke folder `client_files`.
5. Jalankan `client.py` lagi.
6. Sistem hanya mengirim file baru atau file yang berubah.
7. Cek log di `logs/sync_log.csv`.

## Command Tambahan

### Mengganti port server

Server:

```bash
python server.py --host 0.0.0.0 --port 6000
```

Client:

```bash
python client.py --server 127.0.0.1 --port 6000 --folder client_files --client-id client01
```

### Memaksa kirim semua file

```bash
python client.py --server 127.0.0.1 --folder client_files --client-id client01 --force
```

## Catatan Tambahan (Fitur Lanjutan)

Project ini kini dilengkapi dengan fitur:
- **Modern Client GUI (Baru!)**: Disediakan aplikasi Desktop `client_gui.py` berbasis *CustomTkinter* untuk mempermudah sinkronisasi dan manajemen file.
- **Keamanan SSL/TLS**: Enkripsi penuh layaknya HTTPS, mencegah data disadap oleh peretas di jaringan lokal.
- **File Versioning & Restore**: File lama disimpan di `_versions` saat ditimpa atau dihapus. Anda bisa melakukan *Restore* dengan mudah melalui tab "Restore Center" di Client GUI.
- **Mirroring (Hapus Sinkron)**: Jika file dihapus di client, file akan terhapus di server (masuk ke `_versions`).
- **Zlib Compression** untuk efisiensi jaringan
- **Resume Transfer** yang memungkinkan pengiriman file dilanjutkan tanpa harus mengulang dari awal jika terjadi putus koneksi.