# Penjelasan Project

## Judul

Sistem Sinkronisasi File Client-Server Menggunakan TCP Socket dengan Deteksi Perubahan File dan Logging Aktivitas

## Deskripsi Singkat

Project ini membuat aplikasi client-server untuk menyinkronkan file dari folder lokal client ke folder server. Client membaca isi folder lokal, mendeteksi file baru atau file yang berubah menggunakan hash SHA-256, lalu mengirimkan file tersebut ke server melalui TCP Socket. Server menerima file, menyimpannya berdasarkan identitas client, dan mencatat semua aktivitas sinkronisasi ke file log CSV.

## Tujuan

1. Menerapkan konsep client-server pada pemrograman jaringan.
2. Menggunakan TCP Socket sebagai media komunikasi antar aplikasi.
3. Menunjukkan proses transfer file yang andal menggunakan TCP.
4. Menerapkan konsep resource sharing dalam jaringan.
5. Membuat pencatatan aktivitas jaringan melalui file log.

## Batasan Project

1. Sinkronisasi dilakukan dari client ke server.
2. File yang dikirim adalah file baru atau file yang mengalami perubahan.
3. Deteksi perubahan file menggunakan ukuran file, waktu modifikasi, dan hash SHA-256.
4. Sistem melakukan mirroring sinkronisasi, yaitu menghapus file di server secara otomatis jika file di client dihapus.
5. Sistem diuji pada localhost atau jaringan lokal/LAN.

## Alur Kerja Sistem

1. Server dijalankan dan membuka port tertentu.
2. Client membaca seluruh file dalam folder lokal.
3. Client membuat data manifest berisi path file, ukuran file, waktu modifikasi, dan hash SHA-256.
4. Client membandingkan manifest saat ini dengan manifest sebelumnya.
5. File baru atau berubah dikirim ke server.
6. Server menerima metadata file dari client.
7. Server mengecek apakah file sudah pernah diterima dengan hash yang sama.
8. Jika belum ada atau berubah, server meminta client mengirim isi file.
9. Server menyimpan file ke folder `server_storage/<client_id>/`.
10. Server mencatat aktivitas ke `logs/sync_log.csv`.
11. Client menyimpan manifest terbaru ke `.sync_state.json`.

## Materi Pemrograman Jaringan yang Digunakan

### 1. TCP

TCP digunakan karena project ini membutuhkan pengiriman file yang andal. Dalam transfer file, data harus sampai secara utuh, berurutan, dan tidak boleh hilang.

### 2. Socket Programming

Socket digunakan sebagai endpoint komunikasi antara client dan server. Server melakukan bind dan listen pada alamat IP serta port tertentu, sedangkan client melakukan connect ke alamat server.

### 3. Client-Server

Client bertugas membaca file lokal dan mengirim file ke server. Server bertugas menerima file, menyimpan file, dan mencatat log sinkronisasi.

### 4. Resource Sharing

Project ini menerapkan konsep berbagi sumber daya berupa file. File dari client dikirim dan disimpan di server agar dapat menjadi pusat penyimpanan hasil sinkronisasi.

### 5. Network Operating System

Konsep NOS berkaitan dengan server yang melayani permintaan client, pengelolaan file, pengaturan folder, dan pencatatan aktivitas jaringan.

## Skenario Pengujian

| No | Skenario | Langkah | Hasil yang Diharapkan |
|---|---|---|---|
| 1 | Sinkronisasi awal | Jalankan server dan client | Semua file di folder client terkirim ke server |
| 2 | File baru | Tambahkan file baru, jalankan client lagi | Hanya file baru yang terkirim |
| 3 | File berubah | Ubah isi file, jalankan client lagi | File yang berubah terkirim ulang |
| 4 | File tidak berubah | Jalankan client tanpa perubahan | File dilewati atau tidak dikirim ulang |
| 5 | Logging | Cek `logs/sync_log.csv` | Log berisi nama file, ukuran, waktu, dan status |
| 6 | Multi-client | Jalankan client dengan client_id berbeda | Server menyimpan file di folder client yang berbeda |

## Output Project

1. Program server.
2. Program client.
3. Folder hasil sinkronisasi di sisi server.
4. File log aktivitas sinkronisasi.
5. Tampilan status sinkronisasi pada terminal.

## Kelebihan Project

1. **Modern Client GUI**: Client tidak perlu lagi mengetik perintah di terminal. Disediakan aplikasi Desktop `client_gui.py` berbasis *CustomTkinter* yang sangat cantik, intuitif, mendukung *Dark Mode*, dan *cross-platform*.
2. **Keamanan SSL/TLS Tingkat Industri**: Saluran komunikasi antara Client dan Server dienkripsi penuh menggunakan Sertifikat SSL. Data tidak bisa disadap (*sniffing*) oleh peretas di jaringan lokal.
3. Tidak hanya mengirim file biasa, tetapi mendeteksi file baru, file berubah, dan file yang dihapus (Full Mirroring).
4. Memiliki fitur **File Versioning & Restore** (layaknya Dropbox/Google Drive). Jika file ditimpa atau dihapus, server menyimpannya di folder `_versions`. Client bisa menarik kembali file tersebut lewat menu Restore di aplikasi Desktop.
5. Menggunakan Zlib Compression pada tingkat *chunk* (potongan data) saat pengiriman lewat socket untuk menghemat bandwidth.
6. Memiliki fitur Resume Transfer: Jika transfer file besar terputus di tengah jalan, client bisa melanjutkannya tanpa mengulang dari 0%.
7. Menggunakan TCP Socket murni untuk logika jaringan sehingga sesuai dengan materi lapisan transport.
8. Ada logging aktivitas berbentuk CSV di sisi Server sehingga lalu lintas jaringan dan aktivitas sinkronisasi dapat ditelusuri (*audit*).
9. Mendukung banyak client melalui implementasi Threading pada sisi server.
10. Arsitekturnya berbobot untuk proyek akhir jaringan komputer, namun tetap menggunakan 100% Python tanpa Web Framework eksternal (mengandalkan GUI desktop).