# Penjelasan Project

## Judul

Sistem Sinkronisasi File Dua Arah (*Two-Way Sync*) Klien-Server Menggunakan TCP Socket Aman (SSL/TLS), Kompresi Zlib, Deteksi Perubahan File, dan GUI Modern

## Deskripsi Singkat

Project ini membuat aplikasi *client-server* canggih untuk menyinkronkan file secara dua arah (*Two-Way Sync*) antara direktori lokal klien dan direktori pusat peladen (server). Dilengkapi antarmuka grafis (GUI) modern, Klien secara otomatis membandingkan metadata dan *Hash MD5* dari sistem lokal dengan data peladen. Hanya file yang benar-benar baru atau berubah yang akan diunggah (*Upload*) atau diunduh (*Download*) melalui jalur TCP Socket yang dienkripsi menggunakan SSL/TLS. Server mampu menangani ratusan klien sekaligus dengan arsitektur *ThreadPool*, menyimpan data berdasarkan identitas unik setiap klien, serta mengamankan riwayat penghapusan (*versioning*) ke dalam folder karantina. Seluruh lalu lintas aktivitas tercatat rapi ke dalam log.

## Tujuan

1. Menerapkan arsitektur dan konsep *client-server* modern pada pemrograman jaringan.
2. Memanfaatkan TCP Socket sebagai tulang punggung transportasi aliran data file (biner) lintas perangkat.
3. Menciptakan skema *Two-Way Synchronization* yang cerdas, efisien (dengan kompresi Zlib), dan kebal putus-nyambung (*Resume Transfer*).
4. Mengamankan pertukaran privasi data melalui lapisan Transport Layer Security (TLS/SSL).
5. Menerapkan konsep *resource sharing* multiklien tanpa mogok (menggunakan *Threading/ThreadPool*).

## Batasan Project

1. Klien memiliki wewenang untuk meminta daftar status (*Manifest*) dari Server untuk kalkulasi selisih data.
2. Proses pengiriman dan penerimaan (Sinkronisasi Dua Arah) dibatasi hanya pada file yang dikalkulasi sebagai "baru", "berubah", atau "terhapus".
3. Identifikasi kebaruan (*diffing*) dinilai dari kombinasi Ukuran File (*Size*), Waktu Modifikasi (*MTime*), dan Sidik Jari Kriptografis (*Hash MD5*).
4. File yang tertimpa (*conflict*) atau terhapus (*deleted*) oleh pengguna tidak langsung dihancurkan, melainkan dipindahkan ke sub-folder karantina `_versions/` di sisi server.
5. Sistem dan modul keamanan SSL dapat diuji secara bebas (*Self-Signed*) pada localhost (127.0.0.1) maupun melintasi Local Area Network (LAN).

## Alur Kerja Sistem

1. **Inisialisasi Server:** Server `server.py` dijalankan. Server menyiapkan kunci SSL, menciptakan folder dasar `server_storage/` dan memantik *ThreadPoolExecutor* berkapasitas tinggi, lalu mendengarkan koneksi (*Listening*).
2. **Inisialisasi Klien:** Pengguna menjalankan antarmuka grafis `client_gui.py`, memasukkan alamat IP Server serta ID Klien unik miliknya, lalu menekan "Start Sync".
3. **Pertukaran Manifest:** Melalui jalur TCP SSL, Klien meminta peta (*Manifest*) file yang saat ini dipegang oleh Server untuk client tersebut.
4. **Kalkulasi Data Lokal:** Klien meramban folder lokalnya (mengabaikan file dari daftar hitam `.syncignore`), lalu menghitung ulang nilai MD5 setiap file.
5. **Eksekusi 3-Cabang (Upload/Download/Delete):** 
   - **Upload:** File lokal yang lebih baru atau belum ada di Server akan dikompresi (Zlib) dan dikirim ke Server secara terpotong (*Chunk*). Jika putus, proses bisa diteruskan (*Resume*).
   - **Download:** File di Server yang ternyata lebih baru atau belum ada di sisi Klien akan ditarik (diunduh) turun ke penyimpanan lokal.
   - **Delete/Versioning:** File yang hilang di sisi Klien akan dikonfirmasi sebagai "Terhapus", memaksa Server menyingkirkan file salinannya ke direktori rahasia `_versions/`.
6. **Finalisasi:** Setelah seluruh antrean terproses, koneksi diputus, Klien menyimpan memori riwayat sukses di dalam `.sync_state.json`.

## Materi Pemrograman Jaringan yang Digunakan

### 1. TCP (Transmission Control Protocol)
Sifat pengiriman TCP yang *Reliable*, *In-Order*, dan *Error-Checked* sangat krusial dalam pertukaran *blob* data biner (file dokumen, gambar, dll). Jika ada byte yang tertinggal dalam proses *Upload* / *Download*, file otomatis terkorupsi (rusak). Oleh karenanya UDP sama sekali tidak cocok dipakai di sini.

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
| 1 | File Upload Lokal | Buat file baru di sisi Klien, klik *Start Sync* | File otomatis terbaca sebagai `UPLOAD` dan berhasil diamankan ke Server |
| 2 | File Download Server | Letakkan file manual di direktori Server, klik Klien *Start Sync* | File otomatis terbaca sebagai `DOWNLOAD` dan ditarik turun meramaikan direktori Klien |
| 3 | File Dihapus (Klien) | Hapus sebuah file di Klien, jalankan Sinkronisasi | Server memindahkan file tersebut ke folder `_versions/`, bukannya langsung membuangnya |
| 4 | Kinerja Bandwidth Sempit | Sinkronisasi dokumen *text/csv* murni yang berukuran masif | Kompresi algoritma *Zlib* memampatkannya hingga 70% lebih ringan sebelum melintas di jalur jaringan |
| 5 | Koneksi Terputus | Tarik kabel LAN/Matikan internet di tengah `UPLOAD` file 1 GB | Koneksi terputus dengan wajar; Namun saat Klien menekan sinkronisasi lagi, pengiriman tidak diulang dari 0%, melainkan dilanjutkan (*Resume*) |

## Kelebihan Utama Proyek Ini
1. **Modern Client GUI:** Klien memiliki jendela navigasi berbasis *CustomTkinter* yang intuitif dan elegan dengan implementasi *Dark Mode*.
2. **Keamanan SSL/TLS:** Seluruh saluran data dienkripsi, mencegah peretasan dan penyadapan jaringan lokal (*Man-in-the-Middle Attacks*).
3. **Two-Way Sync:** Mampu mengunggah maupun mengunduh file demi menjaga keseimbangan sempurna antar 2 belah pihak layaknya Dropbox.
4. **File Versioning & Restore:** Tidak mengenal kata hilang berkat fitur karantina internal (`_versions/`).
5. **Zlib & Resume Transfer:** Super hemat kuota jaringan dan anti-gagal karena bisa disambung.
6. **Multi-Threaded Server:** Skalabilitas tinggi yang sanggup menghadapi ratusan Klien yang berlomba-lomba mengunggah di detik yang sama.