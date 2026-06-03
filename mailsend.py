import os
import smtplib
import requests
from email.message import EmailMessage
from datetime import datetime

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DB_TUGAS = "31c87d969b0a80e09112dab127df9869"
DB_STUDENT = "35787d969b0a801fbde8f08af80bb608"
EMAIL = "namedauliah@gmail.com"
PASSWORD = os.getenv("EMAIL_PASS")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28" 
}

def get_notion_data(db_id):
    """Mengambil seluruh data dari database Notion."""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    res = requests.post(url, headers=NOTION_HEADERS)
    return res.json().get("results", [])

def tandai_email_terkirim(page_id):
    """Menandai checkbox 'Send by email' menjadi True di Notion."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Send by email": {"checkbox": True}}}
    requests.patch(url, json=payload, headers=NOTION_HEADERS)

def hitung_semester_mahasiswa(entry_year):
    """Menghitung semester berjalan mahasiswa berdasarkan tahun masuk."""
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    if current_month <= 7:
        tahun_akademik = current_year - 1
    else:
        tahun_akademik = current_year
    
    the_year = tahun_akademik - entry_year

    if current_month >= 8 or current_month == 1:
        semester = (the_year * 2) + 1
    else:
        semester = (the_year * 2) + 2
        
    return semester

def kirim_email_kalender(email_tujuan, nama, nama_tugas, matkul, submit, url_tugas):
    """Mengirim email beserta file .ics kalender untuk reminder."""
    dt_start = submit.replace("-", "")[:8]
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
BEGIN:VEVENT
SUMMARY:[{matkul}] Tugas: {nama_tugas}
DTSTART;VALUE=DATE:{dt_start}
DTEND;VALUE=DATE:{dt_start}
DESCRIPTION:Silakan kumpulkan tugas {nama_tugas} pada hari ini.\\n\\nLink Tugas: {url_tugas}
END:VEVENT
END:VCALENDAR"""

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL, PASSWORD)
            
            msg = EmailMessage()
            msg['Subject'] = f'Tugas Terbaru: {matkul} - {nama_tugas}'
            msg['From'] = EMAIL
            msg['To'] = email_tujuan
            
            body_html = f"""
            <html>
            <body>
                <p> Halo, {nama}!</p>
                <p>Cek tugas terbaru dari mata kuliah <b>{matkul}</b>, yang baru diunggah di EduVent!
                <p>🔗 <a href="{url_tugas}" target="_blank"><b>Buka tugasmu!</b></a></p>
                <br>Batas Pengumpulan: {submit}</br>
                <p>📅 <b><i>Klik attachment file deadline.ics untuk menambahkan reminder waktu pengumpulan tugas ke kalendermu!</i></b></p>
                </p>
            </body>
            </html>
            """

            msg.set_content("Aktifkan HTML untuk melihat pesan ini.")
            msg.add_alternative(body_html, subtype='html')

            msg.add_attachment(
                ics_content.encode('utf-8'),
                maintype='text',
                subtype='calendar',
                filename='deadline.ics'
            )

            smtp.send_message(msg)
            return True
            
    except Exception as e:
        print(f"Gagal mengirim notifikasi email ke {email_tujuan}. Error: {e}")
        return False

if __name__ == "__main__":
    print("Memeriksa tugas yang akan dikirim...")
    data_mhs = get_notion_data(DB_STUDENT)
    data_tugas = get_notion_data(DB_TUGAS)

    if not data_mhs:
        print("Gagal mengirim email")
    elif not data_tugas:
        print("Tidak ada tugas di dalam database.")
    else:
        print(f"Terdapat {len(data_tugas)} tugas,yang belum dikirim ke email")
        
        for tugas in data_tugas:
            t_props = tugas["properties"]
            tugas_id = tugas["id"]
            
            try:
                sudah_terkirim = t_props.get("Send by email", {}).get("checkbox", False)
                if sudah_terkirim:
                    continue  
                
                nama_tugas = t_props["Quest"]["title"][0]["text"]["content"] if t_props.get("Quest", {}).get("title") else "Tanpa Nama"
                matkul = t_props["Matakuliah"]["select"]["name"] if t_props.get("Matakuliah", {}).get("select") else "Mata Kuliah Umum"
                submit_str = t_props["Submit"]["date"]["start"] if t_props.get("Submit", {}).get("date") else None
                url_tugas = tugas.get("url", "#")
                semester_tugas = int(t_props["Semester"]["select"]["name"])
                
                if not submit_str:
                    print(f"Tugas '{nama_tugas}' tidak memiliki tanggal Submit, dilewati...")
                    continue
                    
            except (KeyError, TypeError, ValueError) as e:
                continue

            jumlah_diproses = 0
            sukses_email = 0
            gagal_email = 0

            for mhs in data_mhs:
                m_props = mhs["properties"]
                
                try:
                    nama = m_props["Name"]["title"][0]["text"]["content"]
                    email_tujuan = m_props["Email"]["email"]  
                    entry_year_str = m_props["Entry Year"]["select"]["name"]
                    entry_year = int(entry_year_str)
                except (KeyError, TypeError, ValueError):
                    continue
                
                semester_mahasiswa = hitung_semester_mahasiswa(entry_year)
                if semester_tugas != semester_mahasiswa:
                    continue
                
                berhasil = kirim_email_kalender(email_tujuan, nama, nama_tugas, matkul, submit_str, url_tugas)
                jumlah_diproses += 1
                
                if berhasil:
                    sukses_email += 1
                else:
                    gagal_email += 1
            
            if jumlah_diproses > 0 or sukses_email > 0:
                tandai_email_terkirim(tugas_id)
                print(f"✅ Tugas '{nama_tugas}' dikirim ke {jumlah_diproses} student (Sukses: {sukses_email}, Gagal: {gagal_email}) dan telah ditandai di Notion!")
            else:
                print(f"⚠️ Tugas '{nama_tugas}' (Semester {semester_tugas}) tidak dikirim karena tidak ada mahasiswa dengan semester yang cocok.")