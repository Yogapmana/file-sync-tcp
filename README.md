# File Sync TCP

Aplikasi sinkronisasi file dua arah (*two-way sync*) berbasis TCP Socket di Python. Proyek ini dirancang sebagai solusi *cloud storage* lokal yang aman, cepat, dan tangguh—mendukung banyak klien secara bersamaan (*multi-threaded*).

## Daftar Isi
- [Fitur Utama](#fitur-utama)
- [Prasyarat Sistem](#prasyarat-sistem)
- [Arsitektur Sistem](#arsitektur-sistem)
- [Struktur Direktori](#struktur-direktori)
- [Cara Penggunaan](#cara-penggunaan)
- [Troubleshooting](#troubleshooting)
- [Lisensi](#lisensi)

---

## Fitur Utama

- **Two-Way Synchronization:** Menyinkronkan perubahan (penambahan, modifikasi, penghapusan) antara klien dan server secara otomatis. Mampu menangani konflik file dengan aman tanpa menghilangkan data asli.
- **Modern GUI Client:** Dilengkapi dengan antarmuka desktop (`client_gui.py`) berbasis CustomTkinter. Mendukung integrasi *System Tray* untuk menjalankan *auto-sync* di latar belakang.
- **Keamanan SSL/TLS:** Seluruh komunikasi jaringan dienkripsi penuh menggunakan SSL/TLS. Klien mewajibkan validasi sertifikat untuk mencegah serangan *Man-in-the-Middle (MitM)*.
- **File Versioning & Restore:** File yang ditimpa atau dihapus akan diamankan ke dalam folder `_versions` di server. Pengguna dapat me-*restore* file lama langsung melalui GUI.
- **Konfigurasi .syncignore:** Mendukung file `.syncignore` untuk mengabaikan direktori atau file tertentu (seperti file log, atau folder *build*) agar tidak ikut terunggah.
- **Zlib Compression & Resume Transfer:** Kompresi *on-the-fly* untuk menghemat *bandwidth*. Transfer file berukuran besar yang terputus dapat dilanjutkan kembali tanpa harus mengulang dari awal.
- **Performa Tinggi:** Server diimplementasikan menggunakan `ThreadPoolExecutor` dan arsitektur *Clean Code* untuk melayani ribuan koneksi konkuren dengan manajemen memori yang efisien.

---

## Prasyarat Sistem

- **Python:** Versi 3.8 atau lebih baru.
- **Sistem Operasi:** Windows, macOS, atau Linux.
- **OpenSSL:** Diperlukan untuk men-*generate* sertifikat SSL.
- **Dependensi Tambahan:** (tercantum di `requirements.txt`)
  - `customtkinter`
  - `pystray`
  - `Pillow`

---

## Arsitektur Sistem

Proyek ini dibangun di atas raw `socket` dengan menggunakan protokol kustom berukuran tetap (protokol aplikasi) untuk menjamin transfer data yang stabil.

1. **Format Protokol:** Setiap pesan diawali dengan header panjang *fixed* (8 byte) yang memberitahukan ukuran payload JSON.
2. **Payload JSON:** Berisi metadata perintah seperti aksi (`UPLOAD`, `DOWNLOAD`, `DELETE`, `MANIFEST`), nama file, offset transfer, dan lain-lain.
3. **Aliran Data Biner:** Data ditransmisikan dalam format terkompresi zlib secara *chunk-by-chunk* untuk mencegah kehabisan memori RAM saat memproses file berukuran raksasa.
4. **Manajemen Status:** Status sinkronisasi diatur melalui *Manifest (State)* file lokal, mencocokkan *hash* MD5 dengan data di server.

---

## Struktur Direktori

```text
file-sync-tcp-project/
├── client_gui.py       # Aplikasi antarmuka Desktop (GUI)
├── client.py           # Logika utama klien (jaringan & sinkronisasi)
├── server.py           # Logika utama server (jaringan multi-thread)
├── common.py           # Utilitas dan protokol TCP dasar
├── requirements.txt    # Dependensi Python
├── .syncignore         # Aturan pengecualian file untuk klien
├── .gitignore          # Aturan pengecualian Git
└── logs/               # Direktori penyimpanan log aktivitas
```

---

## Cara Penggunaan

### 1. Persiapan SSL (Wajib)

Sebelum menjalankan aplikasi, Anda diwajibkan untuk men-*generate* sertifikat SSL (*Self-Signed*) agar komunikasi klien dan server dapat dienkripsi. Jalankan perintah berikut di dalam direktori proyek:

```bash
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes
```

*Catatan: Pastikan `server.key` dan `server.crt` berada di direktori yang sama dengan `server.py`. Jangan pernah mempublikasikan file `server.key` ke repositori publik.*

### 2. Instalasi Dependensi

```bash
pip install -r requirements.txt
```

### 3. Menjalankan Server

Jalankan skrip server di terminal. Secara default, server akan berjalan di `0.0.0.0:5001`.

```bash
python server.py
```
*Direktori penyimpanan `server_storage/` dan `logs/` akan dibuat secara otomatis saat server pertama kali menerima klien.*

### 4. Menjalankan Klien (Mode GUI)

Cara paling direkomendasikan dan ramah pengguna untuk menggunakan aplikasi ini adalah melalui GUI:

```bash
python client_gui.py
```

Dari antarmuka ini, Anda dapat:
- Mengatur IP Server dan *Client ID*.
- Memilih folder lokal yang akan disinkronisasi.
- Mengaktifkan fitur **Auto-Sync** (latar belakang).
- Me-*restore* file yang terhapus dari server.

### 5. Menjalankan Klien (Mode CLI)

Untuk penggunaan di lingkungan *headless* (seperti VPS atau skrip otomatisasi), gunakan mode CLI:

```bash
python client.py --server 127.0.0.1 --folder client_files --client-id laptop_01
```

- Gunakan *flag* `--force` untuk memaksa sinkronisasi ulang dengan mengabaikan status *cache*.
- Ganti `127.0.0.1` dengan IP *Local Area Network* (LAN) server Anda jika dijalankan pada mesin yang berbeda (contoh: `192.168.1.10`).

---

## Troubleshooting

- **ConnectionRefusedError:** Pastikan `server.py` sudah berjalan dan IP/Port yang diinput pada klien sudah benar. Periksa juga pengaturan Firewall bawaan OS Anda.
- **SSL Error (WRONG_VERSION_NUMBER):** Pastikan server dan klien sama-sama menggunakan (atau tidak menggunakan) SSL. Periksa apakah sertifikat `server.crt` yang digunakan oleh klien adalah sertifikat yang sama yang di-*generate* untuk server.
- **Transfer Terhenti:** Anda dapat menekan *Cancel* atau mematikan skrip, lalu menjalankannya kembali. Fitur *Resume* akan otomatis melanjutkan unggahan dari batas *byte* terakhir yang tersimpan.

---

## Lisensi

Proyek ini dibuat untuk keperluan edukasi dan *open-source*. Anda bebas memodifikasi dan mengembangkan ulang fitur yang ada sesuai kebutuhan.