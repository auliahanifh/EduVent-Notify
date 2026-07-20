import os
from dotenv import load_dotenv
load_dotenv()
import requests
import base64
import time
import json
import re
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DB_TUGAS = "1df473eeecd24c5c9c4b8fa771bda3bc"
DB_STUDENT = "39f333dd1d2880c0ba76eb07f93e0f1a"
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
        print(f"❌ ERROR INFO DB: {db_res.text}")
        return []
        
    data_sources = db_res.json().get("data_sources", [])
    
    if not data_sources:
        url_query = f"https://api.notion.com/v1/databases/{db_id_valid}/query"
    else:
        data_source_id = data_sources[0]["id"]
        url_query = f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    results = []
    has_more = True
    next_cursor = None
    
    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor
            
        res = requests.post(url_query, headers=NOTION_HEADERS, json=payload)
        if res.status_code != 200:
            print(f"❌ ERROR QUERY DB: {res.text}")
            break
            
        data = res.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor", None)
        
    return results

def get_matkul_info(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    res = requests.get(url, headers=NOTION_HEADERS)
    nama_matkul = "Mata Kuliah Tidak Diketahui"
    db_pengumpulan_id = None
    
    if res.status_code == 200:
        data = res.json()
        props = data.get("properties", {})
        for key, val in props.items():
            if val["type"] == "title" and len(val["title"]) > 0:
                nama_matkul = val["title"][0]["text"]["content"]
                break
        achievement_prop = props.get("Achievement", {})
        if achievement_prop.get("type") == "url" and achievement_prop.get("url"):
            url_str = achievement_prop.get("url")
            match = re.search(r'([a-fA-F0-9]{32})', url_str.split('?')[0].replace("-", ""))
            if match:
                db_pengumpulan_id = match.group(1) 
    return nama_matkul, db_pengumpulan_id

def tandai_email_terkirim(page_id):
    """Tandai pemberitahuan email tugas terkirim"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"email": {"checkbox": True}}}
    requests.patch(url, json=payload, headers=NOTION_HEADERS)

def kirim_kalender_asesmen(service, email_tujuan, nama, nama_tugas, matkul, submit_str, url_tugas):
    dt_stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

    if "T" in submit_str:
        dt_obj = datetime.fromisoformat(submit_str.replace('Z', '+00:00'))
        dt_asesmen = dt_obj + timedelta(days=1)
        dt_minus_1h = dt_asesmen - timedelta(hours=1)
        
        if dt_minus_1h.tzinfo:
            dt_utc = dt_minus_1h.astimezone(timezone.utc)
        else:
            tz_jkt = timezone(timedelta(hours=7))
            dt_utc = dt_minus_1h.replace(tzinfo=tz_jkt).astimezone(timezone.utc)
            
        dt_start_ics = dt_utc.strftime('%Y%m%dT%H%M%SZ')
        format_ics_start = f"DTSTART:{dt_start_ics}"
        format_ics_end = f"DTEND:{dt_start_ics}"
        asesmen_display = dt_asesmen.strftime("%d/%m/%Y")
        time_display = dt_asesmen.strftime("%H:%M WIB")
    else:
        dt_start_str = submit_str.replace("-", "")[:8]
        dt_obj = datetime.strptime(dt_start_str, "%Y%m%d")
        
        dt_asesmen = dt_obj + timedelta(days=1)
        dt_start_ics = dt_asesmen.strftime("%Y%m%d")
        
        format_ics_start = f"DTSTART;VALUE=DATE:{dt_start_ics}"
        format_ics_end = f"DTEND;VALUE=DATE:{dt_start_ics}"
        asesmen_display = dt_asesmen.strftime("%d/%m/%Y")
        time_display = "Tidak ada jam spesifik"

    matkul_bersih = matkul.replace(" ", "")
    unique_id = f"asesmen-{matkul_bersih}-{int(time.time())}@eduvent"
    
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EduVent//Integrate Assignment//ID",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{unique_id}",
        f"DTSTAMP:{dt_stamp}",
        f"SUMMARY:[Asesmen {matkul}] {nama_tugas}",
        format_ics_start,
        format_ics_end,
        f"DESCRIPTION:Asesmen tugas {matkul}: {url_tugas}",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    
    ics_content = "\r\n".join(ics_lines)

    try:
        msg = EmailMessage()
        msg['Subject'] = f'Asesmen: {matkul} - {nama_tugas}'
        msg['From'] = EMAIL
        msg['To'] = email_tujuan
        
        body_html = f"""
        <html>
        <body>
            <p>Halo, <b>{nama}</b>!</p>
            <p>Terima kasih sudah mengumpulkan tugas <b>{nama_tugas}</b> pada mata kuliah <b>{matkul}</b> di EduVent!</p>
            <p>Tanggal <b>asesmen</b>: <b>{asesmen_display}</b></p>
            <p>🔗 <a href="{url_tugas}" target="_blank"><b>Buka halaman tugas!</b></a></p>
            <p>Jam: <b>{time_display}</b></p>
            <p>📅 <b><i>Klik Add to Calendar pada Google Calendar atau klik lampiran file asesmen.ics di bawah ini untuk set reminder waktu asesmen ke kalendermu!</i></b></p>
        </body>
        </html>
        """

        msg.set_content("Aktifkan HTML untuk melihat pesan ini.")
        msg.add_alternative(body_html, subtype='html')

        msg.add_attachment(
            ics_content.encode('utf-8'),
            maintype='application',
            subtype='octet-stream',
            filename='asesmen.ics'
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
    print("🚀 MEMERIKSA EDUVENT UNTUK MENGIRIM EMAIL ASESMEN REMINDER")
    
    gmail_service = get_gmail_service()
    
    data_mhs = get_notion_data(DB_STUDENT)
    data_tugas = get_notion_data(DB_TUGAS)

    if not data_mhs or not data_tugas:
        print("Gagal mengambil data mahasiswa atau tugas.")
        exit()
        
    print(f"✅ Berhasil memuat {len(data_mhs)} Mahasiswa dan {len(data_tugas)} Tugas dari Notion.")

    cache_pengumpulan = {}
    cache_matkul = {}

    mhs_dict = {m["id"]: m for m in data_mhs}
    tugas_dict = {t["id"]: t for t in data_tugas}

    matkul_ids = set()
    for t in data_tugas:
        rel_m = t["properties"].get("Matakuliah", {}).get("relation", [])
        if rel_m:
            matkul_ids.add(rel_m[0]["id"])

    for m_id in matkul_ids:
        cache_matkul[m_id] = get_matkul_info(m_id)

    print("\n🔍 Memulai pengecekan pengumpulan di NewSkill...")

    for m_id, info in cache_matkul.items():
        matkul_name, db_kumpul_id = info
        if not db_kumpul_id: continue

        if db_kumpul_id not in cache_pengumpulan:
            cache_pengumpulan[db_kumpul_id] = get_notion_data(db_kumpul_id)
        data_pengumpulan_matkul = cache_pengumpulan[db_kumpul_id]
        
        jumlah_sukses_email = 0
        
        for kumpul in data_pengumpulan_matkul:
            k_props = kumpul["properties"]
            kumpul_id = kumpul["id"]

            sudah_email = k_props.get("email", {}).get("checkbox", False)
            if sudah_email:
                continue 

            rel_student = k_props.get("Student", {}).get("relation", [])
            rel_tugas = k_props.get("Task Quest", {}).get("relation", [])

            if not rel_student or not rel_tugas:
                continue

            mhs_id = rel_student[0]["id"]
            t_id = rel_tugas[0]["id"]

            if mhs_id in mhs_dict and t_id in tugas_dict:
                try:
                    nama = mhs_dict[mhs_id]["properties"]["Nama"]["title"][0]["text"]["content"]
                    email_tujuan = mhs_dict[mhs_id]["properties"]["Email"]["email"]
                    tugas_props = tugas_dict[t_id]["properties"]
                    nama_tugas = tugas_props["Name"]["title"][0]["text"]["content"] if tugas_props.get("Name", {}).get("title") else "Tugas tanpa nama"
                    url_tugas = tugas_dict[t_id].get("url", "#")
                    
                    submit_str = tugas_props["Submit"]["date"]["start"] if tugas_props.get("Submit", {}).get("date") else None
                    if not submit_str: continue 

                    berhasil = kirim_kalender_asesmen(gmail_service, email_tujuan, nama, nama_tugas, matkul_name, submit_str, url_tugas)
                    
                    if berhasil:
                        tandai_email_terkirim(kumpul_id) 
                        jumlah_sukses_email += 1
                    
                    time.sleep(1) 
                    
                except Exception as e:
                    print(f"Error memproses data email untuk {nama}: {e}")
                    continue
        
        if jumlah_sukses_email > 0:
            print(f"  ✅ Total {jumlah_sukses_email} Email Asesmen terkirim untuk mata kuliah {matkul_name}!")
            
    print("\n🎉 Proses sinkronisasi selesai.")