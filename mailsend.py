import os
import requests
import base64
import time
import json
from email.message import EmailMessage
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DB_TUGAS = "1df473eeecd24c5c9c4b8fa771bda3bc"
DB_STUDENT = "a2bc13f4b8c74d938f98434a2a4d6faf"
EMAIL = "namedauliah@gmail.com"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2025-09-03" 
}

def get_gmail_service():
    """Melakukan autentikasi dan mengembalikan service Gmail API."""
    creds = None
    token_env = os.getenv("GMAIL_TOKEN")
    
    if token_env:
        token_dict = json.loads(token_env)
        creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
    elif os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def format_id_notion(notion_id):
    """Menyisipkan tanda strip (-) otomatis agar sesuai standar UUID Notion versi baru"""
    notion_id = str(notion_id).strip()
    if "-" not in notion_id and len(notion_id) == 32:
        return f"{notion_id[:8]}-{notion_id[8:12]}-{notion_id[12:16]}-{notion_id[16:20]}-{notion_id[20:]}"
    return notion_id

def get_notion_data(db_id):
    db_id_valid = format_id_notion(db_id)
    db_url = f"https://api.notion.com/v1/databases/{db_id_valid}"
    db_res = requests.get(db_url, headers=NOTION_HEADERS)
    if db_res.status_code != 200:
        print(f"❌ ERROR AMBIL DB {db_id_valid}: {db_res.text}")
        return []
        
    data_sources = db_res.json().get("data_sources", [])
    if not data_sources:
        return []
        
    data_source_id = data_sources[0]["id"]
    url = f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    res = requests.post(url, headers=NOTION_HEADERS)
    if res.status_code != 200:
        print(f"❌ ERROR NOTION API (DB {db_id_valid}): {res.text}")
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
    """Tandai pemberitahuan email tugas terkirim"""
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

def kirim_email_kalender(service, email_tujuan, nama, nama_tugas, matkul, submit_str, url_tugas):
    """Mengirim notifikasi info tugas mata kuliah menggunakan Gmail API"""
    dt_start = submit_str.replace("-", "")[:8]

    dt_stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    
    matkul_bersih = matkul.replace(" ", "")
    unique_id = f"tugas-{matkul_bersih}-{int(time.time())}@eduvent"
    
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EduVent//Integrate Assignment//ID",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{unique_id}",
        f"DTSTAMP:{dt_stamp}",
        f"SUMMARY:[{matkul}] {nama_tugas}",
        f"DTSTART;VALUE=DATE:{dt_start}",
        f"DTEND;VALUE=DATE:{dt_start}",
        f"DESCRIPTION:Kumpulkan tugas {matkul} ini: {url_tugas}",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    
    ics_content = "\r\n".join(ics_lines)

    try:
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
            maintype='application',
            subtype='octet-stream',
            filename='deadline.ics'
        )
        encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        service.users().messages().send(userId="me", body=create_message).execute()
        return True
            
    except HttpError as error:
        print(f"Terjadi error API saat mengirim ke {email_tujuan}: {error}")
        return False
    except Exception as e:
        print(f"Gagal mengirim notifikasi email ke {email_tujuan}. Error: {e}")
        return False

if __name__ == "__main__":
    print("Menginisialisasi Gmail API...")
    gmail_service = get_gmail_service()
    
    print("Memeriksa tugas yang akan dikirim ke email...")
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
            print("✅ Semua tugas terbaru terkirim ke email")
        else:
            print(f"Terdapat {len(tugas_belum_dikirim)} tugas baru yang perlu dikirim via email.")
            
            for tugas in tugas_belum_dikirim:
                t_props = tugas["properties"]
                tugas_id = tugas["id"]
                
                try:
                    nama_tugas = t_props["Name"]["title"][0]["text"]["content"] if t_props.get("Name", {}).get("title") else "Tugas tanpa nama"
                    rel_matkul = t_props["Matakuliah"]["relation"]
                    if rel_matkul:
                        matkul_id = rel_matkul[0]["id"]
                        if matkul_id not in cache_matkul:
                            cache_matkul[matkul_id] = get_nama_halaman(matkul_id)
                        matkul = cache_matkul[matkul_id]
                    else:
                        matkul = "Matakuliah Kosong"
                    submit_str = t_props["Submit"]["date"]["start"] if t_props.get("Submit", {}).get("date") else None
                    url_tugas = tugas.get("url", "#")
                    rollup_sem = t_props["Sem"]["rollup"] 
                    semester_tugas = 0
                    if rollup_sem["type"] == "array" and len(rollup_sem["array"]) > 0:
                        item_sem = rollup_sem["array"][0]
                        if item_sem["type"] == "number":
                            semester_tugas = int(item_sem["number"])
                        elif item_sem["type"] == "select" and item_sem.get("select"):
                            semester_tugas = int(item_sem["select"]["name"])
                    elif rollup_sem["type"] == "number":
                        semester_tugas = int(rollup_sem["number"])
                    
                    if not submit_str:
                        print(f"Tugas '{nama_tugas}' tidak memiliki tanggal Submit, dilewati...")
                        continue
                    
                    today = datetime.now().date()
                    submit_date = datetime.strptime(submit_str.split("T")[0], "%Y-%m-%d").date()
                    selisih_hari = (submit_date - today).days

                    if selisih_hari < -14:
                        print(f"🔕 Tugas lama tidak diproses fitur notifikasi")
                        tandai_email_terkirim(tugas_id) 
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
                    
                    berhasil = kirim_email_kalender(gmail_service, email_tujuan, nama, nama_tugas, matkul, submit_str, url_tugas)
                    jumlah_diproses += 1
                    
                    if berhasil:
                        sukses_email += 1
                    else:
                        gagal_email += 1
                    time.sleep(1)

                if jumlah_diproses > 0 or sukses_email > 0:
                    tandai_email_terkirim(tugas_id)
                    print(f"✅ Tugas '{nama_tugas}' dikirim ke {jumlah_diproses} student (Sukses: {sukses_email}, Gagal: {gagal_email})")
                else:
                    print(f"⚠️ Tugas '{nama_tugas}' (Semester {semester_tugas}) tidak dikirim karena tidak ada mahasiswa dengan semester yang cocok.")