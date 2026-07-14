# Sistem Sinkronisasi File Client-Server Menggunakan TCP Socket (Enterprise-Grade)

Proyek ini adalah aplikasi tangguh (*robust*) untuk menyinkronkan file dua arah (*Two-Way Sync*) antara client dan server melalui jaringan menggunakan protokol TCP. Sistem ini telah disempurnakan dengan standar praktik industri terbaik (*Best Practices*), menjadikannya lebih dari sekadar tugas kuliah—ini adalah miniatur *Cloud Storage* (seperti Google Drive/Dropbox) yang sesungguhnya!

## 🚀 Fitur Utama & Keunggulan

1. **Two-Way Synchronization (Sinkronisasi Dua Arah)**
   Perubahan di *Client* akan di-*push* ke *Server*, dan perubahan di *Server* akan di-*pull* ke *Client*. Jika ada perubahan di waktu yang sama, sistem otomatis menangani **Conflict** tanpa menghapus file asli.
   
2. **Modern GUI & Background Tray 🖥️**
   Tersedia aplikasi Desktop modern `client_gui.py` berbasis *CustomTkinter*. Aplikasi ini bisa berjalan di latar belakang (System Tray) untuk melakukan **Auto-Sync** setiap 10 detik tanpa mengganggu pekerjaan Anda.

3. **Keamanan SSL/TLS 🔐**
   Semua lalu lintas data antara Client dan Server dienkripsi penuh menggunakan SSL/TLS. *Client* melakukan validasi sertifikat (`CERT_REQUIRED`) untuk mencegah serangan *Man-in-the-Middle (MitM)*.

4. **File Versioning & Pusat Restore ♻️**
   Jika file ditimpa atau dihapus, Server tidak langsung menghilangkannya secara permanen. File tersebut diamankan ke dalam folder `_versions`. Client dapat melihat riwayat versi dan me-*restore* file lama dengan satu klik via GUI.

5. **Dukungan .syncignore 🚫**
   Sama seperti `.gitignore`, Anda dapat membuat file `.syncignore` di folder client agar file-file sampah, *build folder*, atau data rahasia tidak ikut terunggah ke server.

6. **Resume Transfer & Zlib Compression ⚡**
   Jika koneksi terputus saat mentransfer file berukuran 10GB, transfer dapat dilanjutkan (*resume*) dari titik terakhirnya. File juga dikompresi (Zlib) secara *on-the-fly* agar hemat kuota/bandwidth.

7. **Performa Tinggi (Thread Pooling) 🏎️**
   Server menggunakan arsitektur `ThreadPoolExecutor` dan tidak akan mati kehabisan memori meskipun diserang oleh ribuan koneksi masuk secara bersamaan. Log dicatat dengan rapi menggunakan modul profesional `logging` ke file `logs/server.log`.

---

## 📂 Struktur Direktori

```text
file-sync-tcp-project/
├── client_gui.py       # Aplikasi GUI Desktop Client (Modern)
├── client.py           # Core Logika Client Jaringan TCP & Sync
├── server.py           # Core Logika Server TCP Multi-Thread
├── common.py           # Modul helper dan konstanta
├── requirements.txt    # Daftar dependensi Python
├── .syncignore         # Daftar file/folder yang diabaikan client
├── .gitignore          # File untuk mengabaikan server.key/crt di Git
├── server.crt          # Sertifikat SSL Publik Server
├── server.key          # Kunci Privat SSL Server (JANGAN DI-SHARE!)
├── client_files/       # (Contoh) Folder target sinkronisasi di client
├── server_storage/     # Lokasi server menyimpan data per client
└── logs/               # Lokasi penyimpanan log aktivitas
```

---

## 🛠️ Cara Menjalankan

### Persiapan SSL (Wajib untuk Keamanan)
Agar komunikasi aman, pastikan Anda telah men-generate sertifikat SSL lokal (Self-Signed) di folder proyek:
```bash
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes
```
> **Catatan:** Jangan pernah meng-upload file `server.key` ke GitHub!

### 1. Menjalankan Server
Buka terminal dan jalankan server (secara default *listening* di `0.0.0.0:5001`):
```bash
python server.py
```
*Server akan otomatis membuat folder `server_storage` dan `logs/` jika belum ada.*

### 2. Menjalankan Client GUI (Direkomendasikan)
Cara termudah menggunakan aplikasi ini adalah melalui Antarmuka Desktop:
```bash
python client_gui.py
```
Di GUI ini Anda bisa memasukkan IP Server, ID Client, memilih folder, mengaktifkan **Auto-Sync**, dan me-*restore* file dari sampah/versi lama.

### 3. Menjalankan Client via Terminal (CLI Mode)
Jika Anda hanya punya akses terminal (misal di server headless Linux):
```bash
python client.py --server 127.0.0.1 --folder client_files --client-id laptop_rafie
```
- Gunakan `--force` jika ingin memaksa sinkronisasi/upload ulang mengabaikan cache.
- Ganti `127.0.0.1` dengan IP lokal Server jika menggunakan dua perangkat beda dalam 1 jaringan Wi-Fi/LAN.

---

## 🤝 Kontribusi & Kustomisasi
Proyek ini dibangun dari dasar menggunakan raw `socket` di Python. Anda sangat diperbolehkan untuk melakukan modifikasi seperti menambahkan antarmuka Web Dashboard untuk admin server, atau menambahkan sistem Login Database bagi client.