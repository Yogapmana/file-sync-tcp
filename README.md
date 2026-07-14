# File Sync TCP

Aplikasi sinkronisasi file dua arah (*two-way sync*) berbasis TCP Socket di Python. Proyek ini dirancang sebagai solusi *cloud storage* lokal yang aman, cepat, dan tangguh—mendukung banyak klien secara bersamaan (*multi-threaded*).

## Fitur Utama

- **Two-Way Synchronization:** Menyinkronkan perubahan (penambahan, modifikasi, penghapusan) antara klien dan server secara otomatis. Mampu menangani konflik file dengan aman tanpa menghilangkan data asli.
- **Modern GUI Client:** Dilengkapi dengan antarmuka desktop (`client_gui.py`) berbasis CustomTkinter. Mendukung integrasi *System Tray* untuk menjalankan *auto-sync* di latar belakang.
- **Keamanan SSL/TLS:** Seluruh komunikasi jaringan dienkripsi penuh menggunakan SSL/TLS. Klien mewajibkan validasi sertifikat untuk mencegah serangan *Man-in-the-Middle (MitM)*.
- **File Versioning & Restore:** File yang ditimpa atau dihapus akan diamankan ke dalam folder `_versions` di server. Pengguna dapat me-*restore* file lama langsung melalui GUI.
- **Konfigurasi .syncignore:** Mendukung file `.syncignore` untuk mengabaikan direktori atau file tertentu (seperti file log, atau folder *build*) agar tidak ikut terunggah.
- **Zlib Compression & Resume Transfer:** Kompresi *on-the-fly* untuk menghemat *bandwidth*. Transfer file berukuran besar yang terputus dapat dilanjutkan kembali tanpa harus mengulang dari awal.
- **Performa Tinggi:** Server diimplementasikan menggunakan `ThreadPoolExecutor` dan arsitektur *Clean Code* untuk melayani ribuan koneksi konkuren dengan manajemen memori yang efisien.

## Struktur Direktori

```text
file-sync-tcp-project/
├── client_gui.py       # Aplikasi antarmuka Desktop (GUI)
├── client.py           # Logika utama klien (jaringan & sinkronisasi)
├── server.py           # Logika utama server (jaringan multi-thread)
├── common.py           # Utilitas dan konstanta berbagi
├── requirements.txt    # Dependensi Python
├── .syncignore         # Aturan pengecualian file untuk klien
├── .gitignore          # Aturan pengecualian Git
└── logs/               # Direktori penyimpanan log aktivitas
```

## Persiapan

Sebelum menjalankan aplikasi, Anda diwajibkan untuk men-*generate* sertifikat SSL (*Self-Signed*) agar komunikasi klien dan server dapat dienkripsi. Jalankan perintah berikut di dalam direktori proyek:

```bash
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes
```

*Catatan: Pastikan `server.key` dan `server.crt` berada di direktori yang sama dengan `server.py`. Jangan pernah mempublikasikan file `server.key` ke repositori.*

Install dependensi yang dibutuhkan:

```bash
pip install -r requirements.txt
```

## Cara Penggunaan

### 1. Menjalankan Server

Jalankan skrip server di terminal. Secara default, server akan berjalan di `0.0.0.0:5001`.

```bash
python server.py
```
*Direktori `server_storage` dan `logs/` akan dibuat secara otomatis saat pertama kali dijalankan.*

### 2. Menjalankan Klien (Mode GUI)

Cara paling direkomendasikan untuk menggunakan aplikasi ini adalah melalui GUI:

```bash
python client_gui.py
```

Dari antarmuka ini, Anda dapat mengatur IP Server, Client ID, direktori sinkronisasi, dan mengaktifkan fitur Auto-Sync.

### 3. Menjalankan Klien (Mode CLI)

Untuk penggunaan di lingkungan *headless* (tanpa GUI), gunakan mode antarmuka baris perintah (CLI):

```bash
python client.py --server 127.0.0.1 --folder client_files --client-id laptop_01
```

- Gunakan *flag* `--force` untuk memaksa sinkronisasi ulang dengan mengabaikan status *cache*.
- Ganti `127.0.0.1` dengan IP *Local Area Network* (LAN) server Anda jika dijalankan pada mesin yang berbeda.