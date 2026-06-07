import os
import requests
import time
from datetime import datetime
from urllib.parse import quote

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DB_TUGAS = "31c87d969b0a80e09112dab127df9869"
DB_STUDENT = "35787d969b0a801fbde8f08af80bb608"
DB_PENGUMPULAN = "35987d969b0a80b19b19fc9192bcde0e"
WA_TOKEN = os.getenv("WA_TOKEN")

WA_URL = "https://api.fonnte.com/send"
WA_HEADERS = {
    "Authorization": WA_TOKEN, 
}

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28" 
}

def get_notion_data(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    res = requests.post(url, headers=NOTION_HEADERS)
    return res.json().get("results", [])

def tandai_status_notion(page_id, nama_kolom):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {nama_kolom: {"checkbox": True}}}
    res = requests.patch(url, json=payload, headers=NOTION_HEADERS)
    return res.status_code == 200

def kirim_wa(nomor, pesan):
    payload = {
        "target": nomor,
        "message": pesan
    }
    res = requests.post(WA_URL, json=payload, headers=WA_HEADERS)
    time.sleep(2) 
    return res.status_code == 200

def generate_cal_link(nama_tugas, matkul, submit, url_tugas):
    return ""

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

if __name__ == "__main__":
    print("Memeriksa tugas yang akan dikirim...")
    data_mhs = get_notion_data(DB_STUDENT)
    data_tugas = get_notion_data(DB_TUGAS)
    data_pengumpulan = get_notion_data(DB_PENGUMPULAN) 

    today = datetime.now().date()

    for tugas in data_tugas:
        t_props = tugas["properties"]
        tugas_id = tugas["id"]
        
        try:
            nama_tugas = t_props["Quest"]["title"][0]["text"]["content"]
            matkul = t_props["Matakuliah"]["select"]["name"]
            submit = t_props["Submit"]["date"]["start"] if t_props["Submit"].get("date") else None
            url_tugas = tugas.get("url", "#").replace("www.notion.so", "app.notion.com/p")
            smt_tugas = int(t_props["Semester"]["select"]["name"])

            cb_info = t_props.get("info_whatsapp", {}).get("checkbox", False)
            cb_remind = t_props.get("remind_due", {}).get("checkbox", False)
            cb_overdue= t_props.get("remind_overdue", {}).get("checkbox", False)
            
            if not submit: continue
            submit_date = datetime.strptime(submit, "%Y-%m-%d").date()
            selisih_hari = (submit_date - today).days
        except Exception as e:
            continue

        new_notify = not cb_info
        remind_notify = (selisih_hari == 1) and not cb_remind
        overdue_notify = (selisih_hari == -1) and not cb_overdue
        
        if not (new_notify or remind_notify or overdue_notify):
            continue

        print(f"\nMemproses Tugas: {nama_tugas} | Matkul: {matkul}")
            
        sukses_wa = 0
        gagal_wa = 0
        jumlah_diproses = 0

        reminder_send = None

        for mhs in data_mhs:
            m_props = mhs["properties"]
            mhs_id = mhs["id"]
            
            try:
                nama = m_props["Name"]["title"][0]["text"]["content"]
                nomor_wa = m_props["Phone"]["phone_number"]
                entry_year_str = m_props["Entry Year"]["select"]["name"]
                entry_year = int(entry_year_str)
            except (KeyError, TypeError, ValueError):
                continue

            semester_mahasiswa = hitung_semester_mahasiswa(entry_year)
            
            if smt_tugas != semester_mahasiswa:
                continue

            sudah_kumpul = False
            for c in data_pengumpulan:
                c_props = c["properties"]
                rel_student = c_props.get("Student", {}).get("relation", [])
                rel_tugas = c_props.get("Tugas Quest", {}).get("relation", [])
                if rel_student and rel_tugas:
                    if rel_student[0]["id"] == mhs_id and rel_tugas[0]["id"] == tugas_id:
                        sudah_kumpul = True
                        break

            berhasil = False
            dikirim = False
            pesan = ""

            if overdue_notify:
                if not sudah_kumpul: 
                    pesan = f"🚨 Halo *{nama}*, kamu telah melewati batas waktu pengumpulan {nama_tugas} pada mata kuliah *{matkul}*, *nilaimu kosong*! 🚨"
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True
                    reminder_send = "overdue"

            elif remind_notify:
                if sudah_kumpul:
                    pesan = (
                        f"Halo *{nama}*, tugas pada mata kuliah {matkul} yang kamu kerjakan sudah terdaftar dalam EduVent. Segara *kumpulkan juga tugasnya di myITS Classroom*!\n"
                        f"🔗 Cek Tugas: {url_tugas}\n")
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True
                else:
                    pesan = (
                        f"⚠️ Halo *{nama}*, kamu *belum mengumpulkan tugas* pada *mata kuliah {matkul}*! Segera selesaikan pada tautan berikut dan *kumpulkan paling lambat besok*!\n"
                        f"🔗 Cek Tugas: {url_tugas}\n")
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True
                    reminder_send = "remind"

            elif new_notify:
                cal_link = generate_cal_link(nama_tugas, matkul, submit, url_tugas)
                pesan = (
                    f"Halo *{nama}*, kerjakan tugas baru yang telah diunggah di EduVent!\n\n"
                    f"📚 Mata Kuliah: {matkul}\n"
                    f"📅 Deadline: {submit}\n"
                    f"🔗 Tugas: {url_tugas}\n\n"
                    f"Cek email untuk mengaktifkan reminder waktu pengumpulan tugas ke kalendermu!\n"
                )
                berhasil = kirim_wa(nomor_wa, pesan)
                dikirim = True
                reminder_send = "new"


            if dikirim:
                jumlah_diproses += 1
                if berhasil:
                    sukses_wa += 1
                else:
                    gagal_wa += 1
                    
        if jumlah_diproses > 0:
            print(f"📊 Laporan Tugas '{nama_tugas}': Diproses: {jumlah_diproses} | Sukses: {sukses_wa} | Gagal: {gagal_wa}")

            if jenis_notif_dikirim == "overdue":
                tandai_status_notion(tugas_id, "remind_overdue")
                tandai_status_notion(tugas_id, "remind_due")
                tandai_status_notion(tugas_id, "info_whatsapp")
                print("✅ Peringatan tidak mengumpulkan tugas (Overdue) terkirim dan dicentang!")
                
            elif jenis_notif_dikirim == "remind":
                tandai_status_notion(tugas_id, "remind_due")
                tandai_status_notion(tugas_id, "info_whatsapp") # Centang tugas baru juga agar tidak spam di putaran berikutnya
                print("✅ Peringatan pengumpulan tugas (H-1) terkirim dan dicentang!")
                
            elif jenis_notif_dikirim == "new":
                tandai_status_notion(tugas_id, "info_whatsapp")
                print("✅ Berhasil mengirim pemberitahuan tugas terbaru dan dicentang!")
        else:
            if overdue_notify:
                tandai_status_notion(tugas_id, "remind_overdue")
            elif remind_notify:
                tandai_status_notion(tugas_id, "remind_due")
            elif new_notify:
                tandai_status_notion(tugas_id, "info_whatsapp")