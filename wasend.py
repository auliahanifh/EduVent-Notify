import os
import requests
import time
import json
import random
from datetime import datetime

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DB_TUGAS = "1df473eeecd24c5c9c4b8fa771bda3bc"
DB_STUDENT = "a2bc13f4b8c74d938f98434a2a4d6faf"
WA_TOKEN = os.getenv("WA_TOKEN")

WA_URL = "https://api.fonnte.com/send"
WA_HEADERS = {
    "Authorization": WA_TOKEN, 
}

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2025-09-03" 
}

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

def load_jsonc(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        lines = file.readlines()
    clean_lines = []
    for line in lines:
        if not line.strip().startswith("//"): 
            clean_lines.append(line)
    clean_json_string = "".join(clean_lines)
    return json.loads(clean_json_string)

def checked(page_id, nama_kolom):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {nama_kolom: {"checkbox": True}}}
    res = requests.patch(url, json=payload, headers=NOTION_HEADERS)
    if res.status_code != 200:
        print(f"❌ Notion API error {res.status_code}: {res.text}")
        return []
    return res.json().get("results", [])

pesan_terkirim = 0
def kirim_wa(nomor, pesan):
    global pesan_terkirim
    payload = {
        "target": nomor,
        "message": pesan
    }
    res = requests.post(WA_URL, json=payload, headers=WA_HEADERS)
    pesan_terkirim += 1
    if pesan_terkirim >= 30:
        print("⏳ Mencapai batas 30 pesan, istirahat 60 detik untuk mencegah WhatsApp terblokir...")
        time.sleep(60) 
        pesan_terkirim = 0
    else:
        delay = random.triangular(2.0, 8.0, 5.0)
        time.sleep(delay) 
    return res.status_code == 200

def format_nomor_wa(nomor):
    nomor_filter = ''.join(filter(str.isdigit, nomor))
    if nomor_filter.startswith('0'):
        return '62' + nomor_filter[1:]
    elif nomor_filter.startswith('8'):
        return '62' + nomor_filter
    return nomor_filter

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
    print("Memeriksa tugas yang akan dikirim WA...")
    data_mhs = get_notion_data(DB_STUDENT)
    data_tugas = get_notion_data(DB_TUGAS)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    submission_path = os.path.join(base_dir, "db_submission.jsonc")
    map_db_pengumpulan = load_jsonc(submission_path)

    today = datetime.now().date()

    mhs_dict = {m["id"]: m for m in data_mhs}
    tugas_dict = {t["id"]: t for t in data_tugas}

    cache_matkul = {}
    cache_pengumpulan = {}

    for tugas in data_tugas:
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
            submit = t_props["Submit"]["date"]["start"] if t_props["Submit"].get("date") else None
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

            cb_info = t_props.get("1stwhatsapp", {}).get("checkbox", False)
            cb_remind = t_props.get("due", {}).get("checkbox", False)
            cb_overdue = t_props.get("overdue", {}).get("checkbox", False)
            
            if not submit: continue
            submit_date = datetime.strptime(submit.split("T")[0], "%Y-%m-%d").date()
            selisih_hari = (submit_date - today).days
        except Exception:
            continue

        if selisih_hari < -14:
            if not cb_info or not cb_remind or not cb_overdue:
                print(f"🔕 Tugas lama tidak diproses fitur notifikasi")
                
                if not cb_overdue:
                    checked(tugas_id, "overdue")
                if not cb_remind:
                    checked(tugas_id, "due")
                if not cb_info:
                    checked(tugas_id, "1stwhatsapp")
            continue

        db_pengumpulan_id = map_db_pengumpulan.get(matkul)
        if not db_pengumpulan_id:
            print(f"⚠️ Melewati tugas '{nama_tugas}' karena database pengumpulan untuk '{matkul}' tidak tersimpan di database internal!")
            continue

        if db_pengumpulan_id not in cache_pengumpulan:
            cache_pengumpulan[db_pengumpulan_id] = get_notion_data(db_pengumpulan_id)
            
        data_pengumpulan_saat_ini = cache_pengumpulan[db_pengumpulan_id]

        new_notify = not cb_info
        remind_notify = (selisih_hari == 1) and not cb_remind
        overdue_notify = (selisih_hari == -1) and not cb_overdue
        
        if not (new_notify or remind_notify or overdue_notify):
            continue

        mode = None
        if overdue_notify:
            mode = "overdue"
        elif remind_notify:
            mode = "due"
        elif new_notify:
            mode = "new"

        print(f"\nMemproses Tugas: {nama_tugas} | Mata kuliah: {matkul} | Notifikasi: {mode}" )
            
        sukses_wa = gagal_wa = jumlah_diproses = 0

        for mhs in data_mhs:
            m_props = mhs["properties"]
            mhs_id = mhs["id"]
            
            try:
                nama = m_props["Nama"]["title"][0]["text"]["content"]
                nomor_raw = m_props["Phone"]["phone_number"]
                nomor_wa = format_nomor_wa(nomor_raw)
                entry_year_formula = m_props["Entry Year"]["formula"]
                if entry_year_formula["type"] == "string":
                    entry_year = int(entry_year_formula["string"])
                elif entry_year_formula["type"] == "number":
                    entry_year = int(entry_year_formula["number"])
                else:
                    continue
            except Exception:
                continue
            
            if semester_tugas != hitung_semester_mahasiswa(entry_year):
                continue

            sudah_kumpul = False
            for c in data_pengumpulan_saat_ini:
                c_props = c["properties"]
                rel_student = c_props.get("Student", {}).get("relation", [])
                rel_tugas = c_props.get("Task Quest", {}).get("relation", [])
                if rel_student and rel_tugas:
                    if rel_student[0]["id"] == mhs_id and rel_tugas[0]["id"] == tugas_id:
                        sudah_kumpul = True
                        break

            berhasil = dikirim = False

            if mode == "overdue":
                if not sudah_kumpul: 
                    pesan = f"🚨 Halo *{nama}*, kamu *telah melewati* batas waktu *pengumpulan tugas* {nama_tugas} pada mata kuliah *{matkul}*, *nilaimu kosong*! 🚨"
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True

            elif mode == "due":
                if not sudah_kumpul:
                    pesan = (
                        f"⚠️ Halo *{nama}*, kamu *belum mengumpulkan tugas {matkul}*!\n" 
                        f"Segera selesaikan tugasmu pada tautan berikut, dan *kumpulkan paling lambat besok*!\n"
                        f"🔗 Cek tugas: {url_tugas}")
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True

            elif mode == "new":
                pesan = (
                    f"Halo *{nama}*, kerjakan tugas baru yang telah diunggah di EduVent!\n\n"
                    f"📚 Mata Kuliah: {matkul}\n"
                    f"📅 Deadline: {submit}\n"
                    f"🔗 Cek tugas: {url_tugas}\n\n"
                    f"Cek emailmu untuk mengaktifkan reminder waktu pengumpulan tugas ke kalendermu!"
                )
                berhasil = kirim_wa(nomor_wa, pesan)
                dikirim = True

            if dikirim:
                jumlah_diproses += 1
                if berhasil:
                    sukses_wa += 1
                else:
                    gagal_wa += 1
                    
        if jumlah_diproses > 0:
            print(f"📊 Laporan Tugas '{nama_tugas}': Diproses: {jumlah_diproses} | Sukses: {sukses_wa} | Gagal: {gagal_wa}")

            if mode == "overdue":
                checked(tugas_id, "overdue")
                checked(tugas_id, "due")
                checked(tugas_id, "1stwhatsapp")
                print("✅ Peringatan tidak mengumpulkan tugas terkirim!")
                
            elif mode == "due":
                checked(tugas_id, "due")
                checked(tugas_id, "1stwhatsapp") 
                print("✅ Peringatan pengumpulan tugas terkirim!")
                
            elif mode == "new":
                checked(tugas_id, "1stwhatsapp")
                print("✅ Pemberitahuan tugas terbaru terkirim!")
        else:
            if mode == "overdue":
                checked(tugas_id, "overdue")
            elif mode == "due":
                checked(tugas_id, "due")
            elif mode == "new":
                checked(tugas_id, "1stwhatsapp")
    print("\nCek mahasiswa yang sudah mengumpulkan tugas...")
    for matkul_name, db_kumpul_id in map_db_pengumpulan.items():
        time.sleep(0.5)
        if db_kumpul_id not in cache_pengumpulan:
            cache_pengumpulan[db_kumpul_id] = get_notion_data(db_kumpul_id)
            
        data_pengumpulan_matkul = cache_pengumpulan[db_kumpul_id]
        
        for kumpul in data_pengumpulan_matkul:
            k_props = kumpul["properties"]
            kumpul_id = kumpul["id"]

            cb_myits = k_props.get("myits", {}).get("checkbox", False)
            if cb_myits:
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
                    nomor_raw = mhs_dict[mhs_id]["properties"]["Phone"]["phone_number"]
                    nomor_wa = format_nomor_wa(nomor_raw)
                    rel_matkul_kumpul = tugas_dict[t_id]["properties"]["Matakuliah"]["relation"]
                    if rel_matkul_kumpul:
                        m_id = rel_matkul_kumpul[0]["id"]
                        matkul = cache_matkul.get(m_id, get_nama_halaman(m_id)) 
                    else:
                        matkul = "Matakuliah Kosong"
                    url_tugas = tugas_dict[t_id].get("url", "#")
                    pesan_myits = (
                        f"Halo *{nama}*, tugas pada mata kuliah *{matkul}* yang kamu kerjakan sudah terdaftar dalam EduVent.\n"
                        f"Segera *kumpulkan* juga *tugasmu ke myITS Classroom*!\n"
                        f"🔗 Cari tugasmu: {url_tugas}!\n"
                        f"Lalu klik tulisan pada kolom asesmen untuk pengumpulan di myITS Classroom"
                    )

                    if kirim_wa(nomor_wa, pesan_myits):
                        checked(kumpul_id, "myits")
                        print(f"✅Notifikasi pengumpulan myITS terkirim!")
                except Exception as e:
                    print(f"Gagal memproses notif myITS: {e}")