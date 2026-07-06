import os
import time

print("Jalankan server EduVent...")

while True:
    print("Periksa update EduVent terbaru...")
    os.system("python -u wasend.py")
    print("Tunggu 3 menit sebelum pengecekan berikutnya...\n")
    time.sleep(180)