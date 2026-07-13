# Program Integrasi Kustom EduVent

Konfigurasi otomatisasi sistem pemberitahuan dan pengingat tugas melalui WhatsApp dan Email yang terintegrasi dengan database Notion.

## Daftar File

### 1. Notifikasi WhatsApp
* **Fitur Utama:**
  * Mengirimkan pesan WhatsApp peringatan dengan tiga mode: tugas baru, H-1 due date, atau tugas yang tidak dikumpulkan (overdue)[cite: 1].
  * Mengecek status pengumpulan mahasiswa pada database terpisah berdasarkan pemetaan file konfigurasi[cite: 1].
  * Mengirim notifikasi tambahan untuk mengumpulkan tugas ke myITS Classroom jika mahasiswa terdeteksi sudah mengumpulkan tugas di database internal[cite: 1].

### 2. Notifikasi Email & Integrasi Kalender
* **Fitur Utama:**
  * Membuat *event* kalender dalam bentuk file berekstensi `.ics` secara dinamis, berisi judul mata kuliah, nama tugas, deadline, dan link tugas[cite: 2].
  * Mengirimkan pesan email berformat HTML beserta lampiran file `.ics` kepada daftar mahasiswa yang sesuai dengan semester tugas[cite: 2].

### 3. Konfigurasi Pengumpulan Tugas 
* **Fitur Utama:**
  * Sumber referensi file `wasend.py` untuk pengelolaan database penyimpanan tugas pengguna pada setiap mata kuliah[cite: 1].