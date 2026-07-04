import os
import requests
import time
import json
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
    "Notion-Version": "2022-06-28" 
}

def get_notion_data(db_id):
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
    return res.status_code == 200

def kirim_wa(nomor, pesan):
    payload = {
        "target": nomor,
        "message": pesan
    }
    res = requests.post(WA_URL, json=payload, headers=WA_HEADERS)
    time.sleep(2) 
    return res.status_code == 200

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
    print("Memeriksa notif pengumpulan tugas yang akan dikirim...")
    data_mhs = get_notion_data(DB_STUDENT)
    data_tugas = get_notion_data(DB_TUGAS)
    db_pengumpulan = load_jsonc("db_submission.jsonc")

    today = datetime.now().date()

    mhs_dict = {m["id"]: m for m in data_mhs}
    tugas_dict = {t["id"]: t for t in data_tugas}

    cache_matkul = {}

    for tugas in data_tugas:
        t_props = tugas["properties"]
        tugas_id = tugas["id"]
        
        try:
            nama_tugas = t_props["Name"]["title"][0]["text"]["content"]
            rel_matkul = t_props["Matakuliah"]["relation"]
            if rel_matkul:
                matkul_id = rel_matkul[0]["id"]
                if matkul_id not in cache_matkul:
                    cache_matkul[matkul_id] = get_nama_halaman(matkul_id)
                matkul = cache_matkul[matkul_id]
            else:
                matkul = "Matakuliah Kosong"
            rollup_sem = t_props["Sem"]["rollup"] 
            if rollup_sem["type"] == "array" and len(rollup_sem["array"]) > 0:
                smt_tugas = int(rollup_sem["array"][0].get("number", 0))
            elif rollup_sem["type"] == "number":
                smt_tugas = int(rollup_sem["number"])
            else:
                smt_tugas = 0
            submit = t_props["Submit"]["date"]["start"] if t_props["Submit"].get("date") else None
            url_tugas = tugas.get("url", "#")

            cb_info = t_props.get("1stwhatsapp", {}).get("checkbox", False)
            cb_remind = t_props.get("due", {}).get("checkbox", False)
            cb_overdue = t_props.get("overdue", {}).get("checkbox", False)
            
            if not submit: continue
            submit_date = datetime.strptime(submit, "%Y-%m-%d").date()
            selisih_hari = (submit_date - today).days
        except Exceptionas as e:
            print(f"Melewati tugas karena error parsing: {e}")
            continue

        if selisih_hari < -30:
            if not cb_info: checked(tugas_id, "1stwhatsapp")
            if not cb_remind: checked(tugas_id, "due")
            if not cb_overdue: checked(tugas_id, "overdue")
            continue

        new_notify = not cb_info
        remind_notify = (selisih_hari == 1) and not cb_remind
        overdue_notify = (selisih_hari == -1) and not cb_overdue
        
        if not (new_notify or remind_notify or overdue_notify):
            continue

        mode = None
        if overdue_notify: mode = "overdue"
        elif remind_notify: mode = "remind"
        elif new_notify: mode = "new"

        print(f"\nMemproses Tugas: {nama_tugas} | Mata kuliah: {matkul} | Notifikasi: {mode}" )
            
        sukses_wa = gagal_wa = jumlah_diproses = 0

        for mhs in data_mhs:
            m_props = mhs["properties"]
            mhs_id = mhs["id"]
            
            try:
                nama = m_props["Nama"]["title"][0]["text"]["content"]
                nomor_wa = m_props["Phone"]["phone_number"]
                clean_wa = raw_nomor_wa.replace("-", "").replace(" ", "")
                if clean_wa.startswith("0"):
                    nomor_wa = "62" + clean_wa[1:]
                elif clean_wa.startswith("+62"):
                    nomor_wa = clean_wa[1:] 
                else:
                    nomor_wa = clean_wa
                entry_year_formula = m_props["Entry Year"]["formula"]
                if entry_year_formula["type"] == "string":
                    entry_year = int(entry_year_formula["string"])
                elif entry_year_formula["type"] == "number":
                    entry_year = int(entry_year_formula["number"])
                else:
                    continue

            except Exception as e:
                continue
            
            if smt_tugas != hitung_semester_mahasiswa(entry_year):
                continue

            sudah_kumpul = False
            for c in data_pengumpulan:
                c_props = c["properties"]
                rel_student = c_props.get("Student", {}).get("relation", [])
                rel_tugas = c_props.get("Task Quest", {}).get("relation", [])
                status_tugas = c_props.get("Status", {}).get("status", {}).get("name", "Progress")
                
                if rel_student and rel_tugas:
                    if rel_student[0]["id"] == mhs_id and rel_tugas[0]["id"] == tugas_id:
                        if status_tugas == "Done":
                            sudah_kumpul = True
                        break

            berhasil = dikirim = False

            if mode == "overdue":
                if not sudah_kumpul: 
                    pesan = f"🚨 Halo *{nama}*, kamu telah melewati batas waktu pengumpulan *tugas* {nama_tugas} pada mata kuliah *{matkul}*, *nilaimu kosong*! 🚨"
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True

            elif mode == "remind":
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
                    f"🔗 Tugas: {url_tugas}\n\n"
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
                print("✅ Peringatan tidak mengumpulkan tugas (Overdue) terkirim!")
                
            elif mode == "remind":
                checked(tugas_id, "due")
                checked(tugas_id, "1stwhatsapp") 
                print("✅ Peringatan pengumpulan tugas (H-1) terkirim!")
                
            elif mode == "new":
                checked(tugas_id, "1stwhatsapp")
                print("✅ Pemberitahuan tugas terbaru terkirim!")
        else:
            if mode == "overdue":
                checked(tugas_id, "overdue")
            elif mode == "remind":
                checked(tugas_id, "due")
            elif mode == "new":
                checked(tugas_id, "1stwhatsapp")
    print("\nCek mahasiswa yang sudah mengumpulkan tugas...")
    for kumpul in data_pengumpulan:
        k_props = kumpul["properties"]
        kumpul_id = kumpul["id"]

        cb_myits = k_props.get("remind_myits", {}).get("checkbox", False)
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
                nomor_wa = mhs_dict[mhs_id]["properties"]["Phone"]["phone_number"]
                clean_wa = raw_nomor_wa.replace("-", "").replace(" ", "")
                if clean_wa.startswith("0"):
                    nomor_wa = "62" + clean_wa[1:]
                elif clean_wa.startswith("+62"):
                    nomor_wa = clean_wa[1:]
                else:
                    nomor_wa = clean_wa
                matkul = tugas_dict[t_id]["properties"]["Matakuliah"]["relation"]
                if rel_matkul_kumpul:
                    m_id = rel_matkul_kumpul[0]["id"]
                    matkul = cache_matkul.get(m_id, get_nama_halaman(m_id)) 
                else:
                    matkul = "Matakuliah Kosong"
                url_tugas = tugas_dict[t_id].get("url", "#")
                pesan_myits = (
                    f"Halo *{nama}*, tugas pada mata kuliah *{matkul}* yang kamu kerjakan sudah terdaftar dalam EduVent.\n"
                    f"Segera *kumpulkan* juga *tugasmu ke myITS Classroom*!\n"
                    f"🔗 Cek tugas: {url_tugas}"
                )

                if kirim_wa(nomor_wa, pesan_myits):
                    checked(kumpul_id, "remind_myits")
                    print(f"✅ Pemberitahuan pengumpulan myITS Classroom telah terkirim!")
            except Exception as e:
                print(f"Gagal memproses notif myITS: {e}")