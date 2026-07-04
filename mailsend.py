import os
import smtplib
import requests
from email.message import EmailMessage
from datetime import datetime

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DB_TUGAS = "1df473eeecd24c5c9c4b8fa771bda3bc"
DB_STUDENT = "a2bc13f4b8c74d938f98434a2a4d6faf"
EMAIL = "namedauliah@gmail.com"
PASSWORD = os.getenv("APP_PASS")

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

def get_nama_halaman(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    res = requests.get(url, headers=NOTION_HEADERS) 
    if res.status_code == 200:
        data = res.json()
        for key, val in data["properties"].items():
            if val["type"] == "title" and len(val["title"]) > 0:
                return val["title"][0]["text"]["content"]
    return "Mata Kuliah Tidak Diketahui"

def tandai_email_terkirim(page_id):
    """Tandai pemberitahuan tugas terkirim melalui email"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"email": {"checkbox": True}}}
    requests.patch(url, json=payload, headers=NOTION_HEADERS)

def hitung_semester_mahasiswa(entry_year):
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

def kirim_email_kalender(email_tujuan, nama, nama_tugas, matkul, submit_str, url_tugas):
    """Mengirim notifikasi info tugas mata kuliah"""
    dt_start = submit_str.replace("-", "")[:8]
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
BEGIN:VEVENT
SUMMARY:[{matkul}] {nama_tugas}
DTSTART;VALUE=DATE:{dt_start}
DTEND;VALUE=DATE:{dt_start}
DESCRIPTION:Kumpulkan tugas [{matkul}] Tugas: {nama_tugas} hari ini! \\n\\n Cek tugas: {url_tugas}
END:VEVENT
END:VCALENDAR"""

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as smtp:
            smtp.login(EMAIL, PASSWORD)
            
            msg = EmailMessage()
            msg['Subject'] = f'Tugas Terbaru: {matkul} - {nama_tugas}'
            msg['From'] = EMAIL
            msg['To'] = email_tujuan
            
            body_html = f"""
            <html>
            <body>
                <p> Halo, {nama}!</p>
                <p>Cek tugas terbaru dari mata kuliah <b>{matkul}</b> telah diunggah di EduVent!</p>
                <p>🔗 <a href="{url_tugas}" target="_blank"><b>Buka tugasmu!</b></a></p>
                <p>Batas Pengumpulan: <b>{submit_str}</b></p>
                <p>📅 <b><i>Klik attachment file deadline.ics di bawah ini untuk menambahkan reminder waktu pengumpulan tugas {matkul} ke kalendermu!</i></b></p>
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
    print("Memeriksa tugas yang akan dikirim Email...")
    data_mhs = get_notion_data(DB_STUDENT)
    data_tugas = get_notion_data(DB_TUGAS)

    if not data_mhs:
        print("Gagal mengambil data mahasiswa")
    elif not data_tugas:
        print("Tidak ada tugas sama sekali")
    else:
        cache_matkul = {}

        tugas_belum_dikirim = []
        for t in data_tugas:
            sudah_terkirim = t["properties"].get("email", {}).get("checkbox", False)
            if not sudah_terkirim:
                tugas_belum_dikirim.append(t)

        if len(tugas_belum_dikirim) == 0:
            print("✅ Semua tugas sudah dikirim melalui email")
        else:
            print(f"Terdapat {len(tugas_belum_dikirim)} tugas baru yang perlu dikirim via email.")
            
            for tugas in tugas_belum_dikirim:
                t_props = tugas["properties"]
                tugas_id = tugas["id"]
                
                try:
                    nama_tugas = t_props["Nama"]["title"][0]["text"]["content"] if t_props.get("Nama", {}).get("title") else "Tanpa Nama"
                    rel_matkul = t_props["Matakuliah"]["relation"]
                    if rel_matkul:
                        matkul_id = rel_matkul[0]["id"]
                        if matkul_id not in cache_matkul:
                            cache_matkul[matkul_id] = get_nama_halaman(matkul_id)
                        matkul = cache_matkul[matkul_id]
                    else:
                        matkul = "Matakuliah Kosong"
                    submit_str = t_props["Submit"]["date"]["start"] if t_props.get("Submit", {}).get("date") else None
                    url_tugas = tugas.get("url", "#").replace("www.notion.so", "app.notion.com/p")
                    rollup_sem = t_props["Sem"]["rollup"] 
                    if rollup_sem["type"] == "array" and len(rollup_sem["array"]) > 0:
                        semester_tugas = int(rollup_sem["array"][0].get("number", 0))
                    elif rollup_sem["type"] == "number":
                        semester_tugas = int(rollup_sem["number"])
                    else:
                        semester_tugas = 0
                    
                    if not submit_str:
                        print(f"Tugas '{nama_tugas}' tidak memiliki tanggal Submit, dilewati...")
                        continue
                        
                except Exception as e:
                    print(f"Error parsing tugas email: {e}")
                    continue

                jumlah_diproses = sukses_email = gagal_email = 0

                for mhs in data_mhs:
                    m_props = mhs["properties"]
                    
                    try:
                        nama = m_props["Nama"]["title"][0]["text"]["content"]
                        email_tujuan = m_props["Email"]["email"]  
                        entry_year_formula = m_props["Entry Year"]["formula"]
                        if entry_year_formula["type"] == "string":
                            entry_year = int(entry_year_formula["string"])
                        elif entry_year_formula["type"] == "number":
                            entry_year = int(entry_year_formula["number"])
                        else:
                            continue
                    except Exception:
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