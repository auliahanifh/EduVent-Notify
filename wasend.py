import os
from dotenv import load_dotenv
load_dotenv()
import requests
import time
import json
import random
import re
from datetime import datetime

DB_TUGAS = "1df473eeecd24c5c9c4b8fa771bda3bc"
DB_STUDENT = "39f333dd1d2880c0ba76eb07f93e0f1a"
WA_TOKEN = os.getenv("WA_TOKEN")

WA_URL = "https://api.fonnte.com/send"
WA_HEADERS = {
    "Authorization": WA_TOKEN, 
    "Content-Type": "application/json"
}

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2025-09-03" 
}

def format_id_notion(notion_id):
    notion_id = str(notion_id).strip()
    if "-" not in notion_id and len(notion_id) == 32:
        return f"{notion_id[0:8]}-{notion_id[8:12]}-{notion_id[12:16]}-{notion_id[16:20]}-{notion_id[20:32]}"
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
    group_id = None
    
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
        
        grup_prop = props.get("WAgroup", {})
        if grup_prop.get("type") == "rich_text" and len(grup_prop["rich_text"]) > 0:
            group_id = grup_prop["rich_text"][0]["text"]["content"]
    return nama_matkul, db_pengumpulan_id, group_id

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
        print("⏳ Mencapai batas 30 pesan, istirahat 60 detik...")
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

if __name__ == "__main__":
    print("🚀 MEMERIKSA EDUVENT UNTUK MENGIRIM WA")
    
    data_mhs = get_notion_data(DB_STUDENT)
    data_tugas = get_notion_data(DB_TUGAS)
    
    print(f"✅ Berhasil memuat {len(data_mhs)} Mahasiswa dan {len(data_tugas)} Tugas dari Notion.")

    today = datetime.now().date()

    mhs_dict = {m["id"]: m for m in data_mhs}
    tugas_dict = {t["id"]: t for t in data_tugas}

    cache_matkul = {}
    cache_pengumpulan = {}

    tugas_pertama = {}
    baris_kosong = 0
    
    for t in data_tugas:
        t_props = t["properties"]
        t_id = t["id"]
        
        rel_m = t_props.get("Matakuliah", {}).get("relation", [])
        if not rel_m: 
            baris_kosong += 1
            continue
        m_id = rel_m[0]["id"]
        
        tgl_str = t_props.get("Submit", {}).get("date", {})
        if not tgl_str or not tgl_str.get("start"): 
            baris_kosong += 1
            continue
        
        tgl_obj = datetime.strptime(tgl_str["start"].split("T")[0], "%Y-%m-%d").date()
        
        if m_id not in tugas_pertama:
            tugas_pertama[m_id] = {"id": t_id, "date": tgl_obj, "nama": t_props.get("Name", {}).get("title", [{"text":{"content": "Kosong"}}])[0]["text"]["content"]}
        elif tgl_obj < tugas_pertama[m_id]["date"]:
            tugas_pertama[m_id] = {"id": t_id, "date": tgl_obj, "nama": t_props.get("Name", {}).get("title", [{"text":{"content": "Kosong"}}])[0]["text"]["content"]}

    print(f"   (Mengabaikan {baris_kosong} baris tugas yang kosong/tanpa Matkul/tanpa tanggal Submit di Notion)")

    if len(tugas_pertama) == 0 and len(data_tugas) > 0:
        print("\n⚠️ PERINGATAN: Tidak ada satupun tugas yang valid ditemukan!")
        print("Silakan cek apakah nama variabel di Notion persis seperti ini (huruf besar/kecil & spasi):")
        print("1. 'Matakuliah' (Tipe Relation)")
        print("2. 'Submit' (Tipe Date)")
        sample_keys = list(data_tugas[0]["properties"].keys())
        print(f"Kolom yang terbaca oleh program: {sample_keys}\n")

    print("\n🏆 DAFTAR TUGAS PERTAMA TIAP MATAKULIAH:")
    for m_id, info in tugas_pertama.items():
        print(f"   👉 [{info['date']}] {info['nama']}")

    for tugas in data_tugas:
        t_props = tugas["properties"]
        tugas_id = tugas["id"]
        
        try:
            nama_tugas = t_props["Name"]["title"][0]["text"]["content"] if t_props.get("Name", {}).get("title") else "Tugas tanpa nama"
            rel_matkul = t_props["Matakuliah"]["relation"]
            if rel_matkul:
                matkul_id = rel_matkul[0]["id"]
                if matkul_id not in cache_matkul:
                    cache_matkul[matkul_id] = get_matkul_info(matkul_id)
                matkul, db_pengumpulan_id, group_id = cache_matkul[matkul_id]
            else:
                matkul = "Matakuliah Kosong"
                db_pengumpulan_id = None
                group_id = None
                
            submit = t_props["Submit"]["date"]["start"] if t_props.get("Submit", {}).get("date") else None
            url_tugas = tugas.get("url", "#")

            cb_info = t_props.get("add", {}).get("checkbox", False)
            cb_remind = t_props.get("due", {}).get("checkbox", False)
            cb_overdue = t_props.get("overdue", {}).get("checkbox", False)
            
            if not submit: continue
            if "T" in submit:
                dt_obj = datetime.fromisoformat(submit.replace('Z', '+00:00'))
                submit_display = dt_obj.strftime("%d/%m/%Y") 
                time_display = dt_obj.strftime("%H:%M WIB")
                time_text = f"⏰ *Jam*: *{time_display}*\n"
            else:
                dt_obj = datetime.strptime(submit, "%Y-%m-%d")
                submit_display = dt_obj.strftime("%d/%m/%Y")
                time_display = None
                time_text = ""
            submit_date = datetime.strptime(submit.split("T")[0], "%Y-%m-%d").date()
            selisih_hari = (submit_date - today).days
        except Exception as e:
            continue
        
        is_tugas_pertama = (tugas_id == tugas_pertama.get(matkul_id, {}).get("id"))
        
        print(f"🔍 Cek: [{matkul}] {nama_tugas} | Selisih: H{selisih_hari} | Tugas Ke-1: {is_tugas_pertama}")

        if selisih_hari < -14:
            print(f"   ⏩ Skip: Tugas lama, dan anggap selesai")
            if not cb_overdue: checked(tugas_id, "overdue")
            if not cb_remind: checked(tugas_id, "due")
            if not cb_info: checked(tugas_id, "add")
            continue

        if not db_pengumpulan_id:
            print(f"   ⚠️ Skip: Tidak ada link NewSkill di Matakuliah!")
            continue

        if db_pengumpulan_id not in cache_pengumpulan:
            cache_pengumpulan[db_pengumpulan_id] = get_notion_data(db_pengumpulan_id)
        data_pengumpulan_saat_ini = cache_pengumpulan[db_pengumpulan_id]
        
        mahasiswa_terdaftar = set()
        
        if not is_tugas_pertama:
            id_tugas_1 = tugas_pertama.get(matkul_id, {}).get("id")
            for c in data_pengumpulan_saat_ini:
                rel_t = c["properties"].get("Task Quest", {}).get("relation", [])
                rel_s = c["properties"].get("Student", {}).get("relation", [])
                if rel_t and rel_s and rel_t[0]["id"] == id_tugas_1:
                    mahasiswa_terdaftar.add(rel_s[0]["id"])

        grup_notify = not cb_info

        if is_tugas_pertama:
            mhs_new_notify = not cb_info
            mhs_remind_notify = (selisih_hari == 1) and not cb_remind
            mhs_overdue_notify = False 
        else:
            mhs_new_notify = False 
            mhs_remind_notify = (selisih_hari == 1) and not cb_remind
            mhs_overdue_notify = (selisih_hari == -1) and not cb_overdue
            
        if not (mhs_new_notify or mhs_remind_notify or mhs_overdue_notify or grup_notify):
            print(f"⏩Belum waktunya dikirim")
            continue

        mode = None
        if mhs_overdue_notify:
            mode = "overdue"
        elif mhs_remind_notify:
            mode = "due"
        elif mhs_new_notify or grup_notify:
            mode = "new"

        print(f"🎯 Kirim tugas: {mode.upper()}" )
        if group_id and group_notify:
                pesan_ortu = (
                f"Bapak/Ibu, tugas *{nama_tugas}* untuk mata kuliah *{matkul}* telah dibuka!\n\n"
                f"Mohon dukungan Bapak/Ibu sekalian, agar putra/putri dapat mengerjakan tugasnya dengan maksimal!\n"
                f"🔗 Link Tugas: {url_tugas}"
                )
                kirim_wa(group_id, pesan_ortu)
                print(f"✅ Notifikasi Grup Orang Tua terkirim!")
        sukses_wa = gagal_wa = jumlah_diproses = 0

        for mhs in data_mhs:
            m_props = mhs["properties"]
            mhs_id = mhs["id"]
            
            try:
                nama = m_props["Nama"]["title"][0]["text"]["content"]
                nomor_raw = m_props["Phone"]["phone_number"]
                nomor_wa = format_nomor_wa(nomor_raw)
            except Exception:
                continue

            if not is_tugas_pertama and mhs_id not in mahasiswa_terdaftar:
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
            
            if mode == "overdue" and mhs_overdue_notify:
                if not sudah_kumpul: 
                    pesan = f"🚨 Halo *{nama}*, kamu *telah melewati* batas waktu *pengumpulan tugas* {nama_tugas} pada mata kuliah *{matkul}*, *nilaimu kosong*! 🚨"
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True

            elif mode == "due" and mhs_remind_notify:
                if not sudah_kumpul:
                    pesan = (
                        f"⚠️ Halo *{nama}*, kamu *belum mengumpulkan tugas {matkul}*!\n" 
                        f"Segera selesaikan tugasmu pada tautan berikut, dan *kumpulkan paling lambat besok*!\n"
                        f"{time_text}\n"
                        f"🔗 Cek tugas: {url_tugas}")
                    berhasil = kirim_wa(nomor_wa, pesan)
                    dikirim = True

            elif mode == "new" and mhs_new_notify:
                pesan = (
                    f"Halo *{nama}*, kerjakan tugas terbaru ini di EduVent!\n\n"
                    f"📚 Mata Kuliah: {matkul}\n"
                    f"📅 *Deadline*: *{submit_display}*\n"
                    f"{time_text}"
                    f"🔗 Cek tugas: {url_tugas}\n\n"
                    f"Abaikan pesan jika kamu tidak mengambil mata kuliah ini"
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
            print(f"   📊 Diproses: {jumlah_diproses} Mahasiswa | Sukses: {sukses_wa} | Gagal: {gagal_wa}")

            if mode == "overdue":
                checked(tugas_id, "overdue")
                checked(tugas_id, "due")
                checked(tugas_id, "add")
            elif mode == "due":
                checked(tugas_id, "due")
                checked(tugas_id, "add") 
            elif mode == "new":
                checked(tugas_id, "add")
        else:
            print("   ⏩ Opt-in kosong / Semua sudah kumpul. Tidak ada WA dikirim.")
            if mode == "overdue": checked(tugas_id, "overdue")
            elif mode == "due": checked(tugas_id, "due")
            elif mode == "new": checked(tugas_id, "add")
                
    print("CEK SUBMIT UNTUK ASESMEN DI MYITS")
    
    for m_id, info in cache_matkul.items():
        matkul_name, db_kumpul_id, group_id = info
        if not db_kumpul_id: continue

        time.sleep(0.5)

        if db_kumpul_id not in cache_pengumpulan:
            cache_pengumpulan[db_kumpul_id] = get_notion_data(db_kumpul_id)
        data_pengumpulan_matkul = cache_pengumpulan[db_kumpul_id]

        jumlah_sukses_myits = 0
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
                        matkul = cache_matkul.get(m_id, get_matkul_info(m_id))[0]
                    else:
                        matkul = "Matakuliah Kosong"
                    url_tugas = tugas_dict[t_id].get("url", "#")
                    
                    submit_str = tugas_dict[t_id]["properties"]["Submit"]["date"]["start"] if tugas_dict[t_id]["properties"].get("Submit", {}).get("date") else None
                    if submit_str:
                        submit_date = datetime.strptime(submit_str.split("T")[0], "%Y-%m-%d").date()
                        selisih_kumpul = (submit_date - today).days
                        
                        if selisih_kumpul >= 0:
                            pesan_myits = (
                                f"Halo *{nama}*, terima kasih sudah mengumpulkan tugas pada mata kuliah *{matkul}* di EduVent!\n"
                                f"Segera lakukan *Asesmen* ke *myITS Classroom* ya!\n"
                                f"🔗 Cari tugasmu dan klik tulisan pada kolom asesmen: {url_tugas}!\n"
                                f"Jika Asesmen belum dibuka, cek emailmu untuk set reminder Asesmen!"
                            )

                            if kirim_wa(nomor_wa, pesan_myits):
                                checked(kumpul_id, "myits")
                                jumlah_sukses_myits += 1
                        else:
                            print(f"⏩ Lewati ucapan Asesmen: Mahasiswa {nama} telat mengumpulkan tugas.")
                            checked(kumpul_id, "myits")  
                except Exception as e:
                    continue
            if jumlah_sukses_myits > 0:
                print(f"   ✅ Notifikasi Asesmen myITS untuk mata kuliah {matkul_name} sukses terkirim ke {jumlah_sukses_myits} mahasiswa!")