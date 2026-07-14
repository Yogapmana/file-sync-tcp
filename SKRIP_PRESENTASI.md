# Pembagian Materi Video Presentasi

**Jumlah Anggota:** 3 Orang
**Konsep:** Presentasi Teknis dan Demonstrasi *Live* Aplikasi Sinkronisasi File.

---

## 1. Orang Pertama: Pengantar & Konsep Dasar (Durasi: ~2 Menit)
**Tugas Utama:** Membuka presentasi dan memberikan gambaran besar (*Big Picture*) tentang aplikasi yang dibuat.

**Poin-poin yang dibahas:**
*   **Pembukaan:** Salam pembuka, perkenalan nama kelompok dan anggota.
*   **Latar Belakang:** Menjelaskan secara ringkas apa itu aplikasi Sinkronisasi File Dua Arah (*Two-Way Sync*) yang tim buat (mirip konsep sistem Dropbox/Google Drive).
*   **Tujuan Proyek:** Menyebutkan bahwa proyek ini bertujuan mengimplementasikan arsitektur *Client-Server* dan *Resource Sharing*.
*   **Mengapa Pakai TCP?** Menjelaskan bahwa aplikasi ini dibangun murni di atas TCP Socket karena sifatnya yang *reliable* dan *error-checked* (sangat penting agar file tidak rusak/korup saat dikirim).
*   **Transisi:** Menyerahkan penjelasan teknis arsitektur kepada Orang Kedua.

## 2. Orang Kedua: Arsitektur & Fitur Unggulan (Durasi: ~3 Menit)
**Tugas Utama:** Menjelaskan "otak" dan sisi teknis jaringan yang menjadi kebanggaan (*selling point*) dari aplikasi ini.

**Poin-poin yang dibahas:**
*   **Kinerja Server (Multi-Threading):** Menjelaskan bahwa server dibangun menggunakan `ThreadPoolExecutor` sehingga bisa melayani puluhan klien yang terhubung secara bersamaan tanpa membuat server mogok.
*   **Keamanan Jaringan (SSL/TLS):** Menekankan bahwa TCP Socket biasa sangat rentan disadap, sehingga tim kalian membungkusnya dengan enkripsi SSL/TLS menggunakan sertifikat kriptografi agar aman.
*   **Efisiensi Jaringan (Zlib & Resume):** Menyebutkan inovasi penghematan *bandwidth* karena data biner dikompresi (Zlib) sebelum dikirim, serta bisa di-*resume* jika koneksi tiba-tiba putus.
*   **Integritas Data (Protokol Kustom):** Menyebutkan secara singkat metode *Length-Prefixed* (memberi awalan ukuran byte pada setiap pesan JSON/Biner) agar pesan di jaringan tidak bertabrakan (*Stream Boundary*).
*   **Transisi:** Menyerahkan panggung untuk pembuktian praktik aplikasi kepada Orang Ketiga.

## 3. Orang Ketiga: Demonstrasi (*Live Demo*) & Penutup (Durasi: ~4 Menit)
**Tugas Utama:** Melakukan *Share Screen* atau perekaman layar untuk mendemonstrasikan kelancaran UI/UX aplikasi dan fitur utamanya, lalu menutup acara.

**Poin-poin yang dibahas (Skenario Demo):**
*   **Inisialisasi:** Memperlihatkan langkah menyalakan `server.py` di terminal (memperlihatkan folder `server_storage/` dan `logs/` otomatis dibuat). Lalu membuka aplikasi `client_gui.py`.
*   **Demo *Upload* (Deteksi File Baru):** Membuat/memasukkan file dokumen ke dalam folder klien, lalu menekan tombol biru *Start Sync* di GUI. Tunjukkan log di GUI berjalan, dan file berhasil terkirim ke Server.
*   **Demo *Delete* & *Versioning* (Penyelamat Data):** Menghapus file tersebut di folder Klien, lalu klik *Start Sync* lagi. Perlihatkan kepada dosen bahwa Server tidak bodoh dengan menghapus file tersebut secara permanen, melainkan memindahkannya ke dalam folder karantina `_versions/` lengkap dengan stempel waktunya.
*   **Kesimpulan & Penutup:** Menyimpulkan bahwa kombinasi protokol jaringan mentah (TCP) bisa diolah menjadi aplikasi modern (ber-GUI), efisien, dan aman. Mengakhiri presentasi dengan salam.
