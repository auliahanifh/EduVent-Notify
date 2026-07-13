# Program Integrasi Kustom EduVent

Konfigurasi otomatisasi sistem pemberitahuan dan pengingat tugas melalui WhatsApp dan Email yang terintegrasi dengan database Notion.

### Notifikasi WhatsApp
  * Mengirimkan pesan WhatsApp peringatan dengan tiga mode: tugas baru, H-1 due date, atau tugas yang tidak dikumpulkan (overdue).
  * Mengecek status pengumpulan mahasiswa pada database terpisah berdasarkan pemetaan file konfigurasi.
  * Mengirim notifikasi tambahan untuk mengumpulkan tugas ke myITS Classroom jika mahasiswa terdeteksi sudah mengumpulkan tugas di database internal.

### Notifikasi Email & Integrasi Kalender
  * Membuat *event* kalender dalam bentuk file berekstensi `.ics` secara dinamis, berisi judul mata kuliah, nama tugas, deadline, dan link tugas.
  * Mengirimkan pesan email berformat HTML beserta lampiran file `.ics` kepada daftar mahasiswa yang sesuai dengan semester tugas.
