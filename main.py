import os
import time

print("Jalankan server EduVent...")

while True:
    print("Cek update tugas terbaru di EduVent...")
    os.system("python -u mailsend.py")
    os.system("python -u wasend.py")
    print("Jeda 3 menit sebelum pengecekan selanjutnya...\n")
    time.sleep(180)