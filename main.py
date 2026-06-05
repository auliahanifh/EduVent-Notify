import os
import time

print("Jalankan server EduVent...")

while True:
    print("Periksa update terbaru...")
    
    os.system("python mailsend.py")
    os.system("python wasend.py")
    
    print("Tunggu satu hari sebelum pengecekan berikutnya...\n")
    
    time.sleep(300)