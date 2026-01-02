import streamlit as st
import os
import json
import glob
import time
import shutil
import signal
import pandas as pd
import datetime
import math
import google.generativeai as genai
import exiftool 
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from streamlit_option_menu import option_menu 
from dotenv import load_dotenv 

# [FIX] Paksa baca ulang .env setiap kali reload agar update real-time
load_dotenv(override=True)

# Import Modul Buatan Sendiri
from config import (
    MODEL_PRICES, PROMPT_PRESETS, PROVIDERS, 
    DEFAULT_INTERNAL_OUTPUT, BASE_WORK_DIR,
    EXIFTOOL_PATH 
)
from database import (
    init_db, 
    add_history_entry, get_history_df, clear_history,
    add_prompt_history, get_prompt_history_df, clear_prompt_history,
    get_recent_history,
    get_paginated_history, update_history_entry
)
from utils import calculate_cost, select_folder_from_wsl, construct_prompt_template, clean_filename
from processor import process_single_file

# [FIXED IMPORT SECTION]
from image_ops import create_xmp_sidecar, compute_dhash, calculate_similarity_percentage
from ai_engine import run_gemini_engine, run_openai_compatible_engine

# [WRAPPER FOR MULTIPROCESSING]
def get_file_hash_wrapper(fpath):
    try:
        return fpath, compute_dhash(fpath)
    except:
        return fpath, None

# Init Database & Folder
init_db()
if not os.path.exists(DEFAULT_INTERNAL_OUTPUT):
    try: os.makedirs(DEFAULT_INTERNAL_OUTPUT)
    except: pass

# ================= PERSISTENT SETTINGS MANAGEMENT =================
SETTINGS_FILE = "user_settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_settings(key, value):
    settings = load_settings()
    settings[key] = value
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

# Load saved path or default
saved_settings = load_settings()
default_temp = saved_settings.get("temp_folder", BASE_WORK_DIR)

# STATE: Gallery Pagination & Search
if 'gallery_page' not in st.session_state: st.session_state['gallery_page'] = 1
if 'gallery_search' not in st.session_state: st.session_state['gallery_search'] = ""

if 'temp_folder_path' not in st.session_state: 
    st.session_state['temp_folder_path'] = default_temp

# Restore Output Folder dari setting
if 'selected_output_path' not in st.session_state:
    st.session_state['selected_output_path'] = saved_settings.get("output_folder", "")

def handle_temp_picker():
    path = select_folder_from_wsl("WAJIB PILIH FOLDER DI DRIVE D: (INTERNAL)")
    if path: 
        st.session_state['temp_folder_path'] = path
        save_settings("temp_folder", path) 

def handle_output_picker():
    path = select_folder_from_wsl("Pilih Folder TUJUAN (Disarankan Drive D:)")
    if path: 
        st.session_state['selected_output_path'] = path
        save_settings("output_folder", path)

def update_manual_input_path():
    st.session_state['selected_folder_path'] = st.session_state['manual_in_text']

def update_manual_output_path():
    path = st.session_state['manual_out_text']
    st.session_state['selected_output_path'] = path
    save_settings("output_folder", path)

def update_preset():
    selected = st.session_state.preset_selector
    st.session_state['active_preset_name'] = selected
    st.session_state['active_title_rule'] = PROMPT_PRESETS[selected]['title']
    st.session_state['active_desc_rule'] = PROMPT_PRESETS[selected]['desc']

# ================= HELPER FUNCTION: EXIFTOOL WRITER =================
def flush_metadata_queue(queue_list):
    if not queue_list: return
    
    et_path = EXIFTOOL_PATH 
    if not et_path and os.name != 'nt': et_path = "exiftool"

    try:
        with exiftool.ExifToolHelper(executable=et_path) as et:
            for item in queue_list:
                src_file = item.pop('SourceFile') 
                try:
                    et.set_tags(
                        src_file, 
                        tags=item, 
                        params=["-overwrite_original", "-codedcharacterset=utf8", "-sep", ", "]
                    )
                except Exception as e_inner:
                    print(f"Failed to write meta for {src_file}: {e_inner}")
                    
    except Exception as e:
        print(f"Metadata Write Error: {e}")

# ================= HELPER FUNCTION: PREPARE CSV DATA =================
def prepare_csv_rows(res):
    today_date = datetime.date.today().strftime("%Y-%m-%d")
    now_time = datetime.datetime.now().strftime("%H:%M:%S")
    is_illustration = "Yes" if res.get('file_type') == "Vector" else "No"
    
    row_master = {
        "Filename": res['new_name'],
        "Original Filename": res['file'],
        "Title": res['meta_title'],
        "Description": res['meta_desc'],
        "Keywords": res['meta_kw'],
        "Category": res['category'],
        "Type": res.get('file_type', 'Other'),
        "Date": today_date, "Time": now_time,
        "Releases": "", "Country": "", "Editorial": "No", "Mature Content": "No", "Illustration": is_illustration
    }
    row_adobe = {
        "Filename": res['new_name'], "Title": res['meta_title'], "Keywords": res['meta_kw'], "Category": res['category'], "Releases": "" 
    }
    row_getty = {
        "file name": res['new_name'], "created date": today_date, "description": res['meta_desc'], "country": "", "brief code": "", "title": res['meta_title'], "keywords": res['meta_kw']
    }
    row_shutter = {
        "Filename": res['new_name'], "Description": res['meta_desc'], "Keywords": res['meta_kw'], "Categories": res['category'], "Editorial": "No", "Mature content": "No", "illustration": is_illustration
    }
    return row_master, row_adobe, row_getty, row_shutter

# ================= HELPER: REGENERATE METADATA =================
def regenerate_metadata_and_rename(file_path, correction_prompt, api_key, model_name, active_rules):
    try:
        source_dir = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        
        provider = "Google Gemini (Native)" 
        base_url = None
        base_prompt = construct_prompt_template(active_rules['title'], active_rules['desc'])
        opts = {"rename": True, "blur_check": False} 

        res = process_single_file(
            filename=filename,
            provider=provider,
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            max_retries=1,      
            options=opts,
            full_prompt=base_prompt,
            source_dir=source_dir,
            custom_temp_dir=st.session_state.get('temp_folder_path', BASE_WORK_DIR),
            blur_threshold=0.0,
            user_correction=correction_prompt 
        )

        if res['status'] == 'error':
            return False, f"AI Error: {res['msg']}", None
        
        et_path = EXIFTOOL_PATH
        if not et_path and os.name != 'nt': et_path = "exiftool"

        with exiftool.ExifToolHelper(executable=et_path) as et:
            et.set_tags(
                file_path, 
                tags=res['tags_data'], 
                params=["-overwrite_original", "-codedcharacterset=utf8", "-sep", ", "]
            )

        new_filename = res['new_name']
        new_file_path = os.path.join(source_dir, new_filename)
        
        if filename != new_filename:
            try:
                shutil.move(file_path, new_file_path)
                old_xmp = os.path.splitext(file_path)[0] + ".xmp"
                if os.path.exists(old_xmp): os.remove(old_xmp)
            except Exception as e:
                print(f"Rename failed: {e}")
                new_file_path = file_path

        kw_list = res['tags_data'].get('XMP:Subject', [])
        create_xmp_sidecar(
            os.path.splitext(new_file_path)[0], 
            res['meta_title'], 
            res['meta_desc'], 
            kw_list
        )
        
        update_history_entry(
            old_filename_in_db=filename, 
            new_filename=new_filename, 
            title=res['meta_title'], 
            desc=res['meta_desc'], 
            keywords=res['meta_kw']
        )
        
        return True, {
            "title": res['meta_title'], 
            "desc": res['meta_desc'], 
            "kw": kw_list
        }, new_file_path
        
    except Exception as e:
        return False, str(e), None

# ================= UI HELPER: MINIMALIST GALLERY CARD =================
def render_minimal_card(row, idx):
    full_path = os.path.join(row['output_path'], row['new_filename'])
    file_exists = os.path.exists(full_path)
    
    with st.container(border=True):
        if file_exists:
            try:
                st.image(full_path, use_container_width=True)
            except:
                st.warning("Preview Error")
        else:
            st.error("File Moved/Deleted")
            
        st.caption(f"**{row['new_filename'][:20]}...**")
        
        with st.popover("✏️ Edit / Detail", use_container_width=True):
            st.markdown(f"**Current Title:** {row['title']}")
            st.caption(f"**Desc:** {row['description']}")
            st.text_area("Keywords", row['keywords'], height=60, disabled=True)
            
            if file_exists:
                st.markdown("---")
                st.markdown("#### 🔄 Regenerate Metadata")
                correction_input = st.text_area("Instruksi Revisi", placeholder="Contoh: Ubah jadi bahasa Indonesia...", key=f"corr_{row['id']}")
                
                if st.button("Proses Revisi ✨", key=f"btn_rev_{row['id']}", type="primary"):
                    if not correction_input:
                        st.toast("⚠️ Isi instruksi revisi dulu!")
                    else:
                        api_key = st.session_state.get('active_api_key_for_correction') 
                        model = st.session_state.get('active_model_for_correction', 'gemini-1.5-flash')
                        rules = {
                            'title': st.session_state.get('active_title_rule', ''),
                            'desc': st.session_state.get('active_desc_rule', '')
                        }
                        
                        if not api_key:
                            st.error("API Key belum diset! Harap set di menu Metadata Auto terlebih dahulu.")
                        else:
                            with st.spinner("Sedang merevisi metadata & database..."):
                                success, res, new_path = regenerate_metadata_and_rename(full_path, correction_input, api_key, model, rules)
                                if success:
                                    st.success("Berhasil! Database Updated.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Gagal: {res}")


# ================= KONFIGURASI HALAMAN & CSS =================
st.set_page_config(page_title="Gemini Studio", page_icon="✨", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container {padding-top: 4rem; padding-bottom: 2rem;}
    div[data-testid="stSidebar"] button[kind="secondary"] {
        font-size: 20px; font-weight: bold; border: none; background: transparent; text-align: left; padding-left: 0; margin-bottom: 0px;
    }
    .stTextArea textarea {font-family: monospace; font-size: 12px;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# ================= STATE MANAGEMENT =================
DEFAULT_PRESET_KEY = "Commercial (Standard) - BEST SELLER"
if 'active_preset_name' not in st.session_state:
    st.session_state['active_preset_name'] = DEFAULT_PRESET_KEY
    st.session_state['active_title_rule'] = PROMPT_PRESETS[DEFAULT_PRESET_KEY]['title']
    st.session_state['active_desc_rule'] = PROMPT_PRESETS[DEFAULT_PRESET_KEY]['desc']

if 'menu_index' not in st.session_state: st.session_state['menu_index'] = 0 
if 'selected_folder_path' not in st.session_state: st.session_state['selected_folder_path'] = ""

if 'watching' not in st.session_state: st.session_state['watching'] = False
if 'nav_key' not in st.session_state: st.session_state['nav_key'] = 0
if 'processed_session_count' not in st.session_state: st.session_state['processed_session_count'] = 0

if 'prompt_results_text' not in st.session_state: st.session_state['prompt_results_text'] = ""
if 'clean_file_list' not in st.session_state: st.session_state['clean_file_list'] = []

def force_navigate(index):
    st.session_state['menu_index'] = index
    st.session_state['nav_key'] += 1 
    st.rerun()

def handle_input_picker():
    path = select_folder_from_wsl("Pilih Folder SUMBER (Drive D:)")
    if path: st.session_state['selected_folder_path'] = path

def force_save_all_settings():
    save_settings("temp_folder", st.session_state.get('temp_folder_path', BASE_WORK_DIR))
    if st.session_state.get('selected_output_path'):
        save_settings("output_folder", st.session_state['selected_output_path'])

# ================= TOP NAVIGATION BAR =================
with st.container():
    selected_menu = option_menu(
        menu_title=None, 
        options=["Gallery", "Metadata Auto", "Prompt Architect", "History Log"], 
        icons=['images', 'camera', 'magic', 'clock'], 
        default_index=st.session_state['menu_index'],
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent", "margin-bottom": "10px"},
            "icon": {"color": "#555", "font-size": "14px"}, 
            "nav-link": {"font-size": "14px", "text-align": "center", "margin": "0px 6px", "padding": "8px 12px", "--hover-color": "#f0f2f6", "font-weight": "500", "color": "#444"},
            "nav-link-selected": {"background-color": "#FF4B4B", "color": "white", "border-radius": "20px", "font-weight": "600", "box-shadow": "0px 2px 4px rgba(0,0,0,0.15)"},
        },
        key=f"top_nav_{st.session_state['nav_key']}" 
    )

menu_map = {"Gallery": 0, "Metadata Auto": 1, "Prompt Architect": 2, "History Log": 3}
if selected_menu in menu_map: st.session_state['menu_index'] = menu_map[selected_menu]

# ================= SIDEBAR =================
with st.sidebar:
    if st.button("✨ Gemini Studio", type="secondary", help="Back to Gallery"):
        force_navigate(0)
    st.markdown("---") 
    st.markdown("### ⚙️ System Config")
    
    active_api_key = None 
    
    # API KEY SETUP (Global / Shared)
    with st.expander("🤖 AI Provider Setup", expanded=True):
        st.caption("Select AI Brain")
        provider_choice = st.selectbox("Provider", list(PROVIDERS.keys()), index=0, label_visibility="collapsed")
        current_provider_config = PROVIDERS[provider_choice]
        env_var_name = current_provider_config.get("env_var")
        detected_key = os.getenv(env_var_name) if env_var_name else None
        model_label = st.selectbox("Model Version", list(current_provider_config["models"].keys()))
        
        if st.checkbox("Use Custom Model ID"):
            final_model_name = st.text_input("Enter Model ID", value=current_provider_config["models"][model_label])
        else:
            final_model_name = current_provider_config["models"][model_label]
        
        st.caption(f"API Key ({provider_choice})")
        active_api_key = st.text_input("API Key", value=detected_key if detected_key else "", type="password", key=f"apikey_{provider_choice}")
        
        st.session_state['active_api_key_for_correction'] = active_api_key
        st.session_state['active_model_for_correction'] = final_model_name
        
        if env_var_name and not detected_key: st.warning(f"⚠️ Missing in .env")

    if selected_menu == "Metadata Auto":
        with st.expander("⚡ Performance", expanded=False):
            num_workers = st.slider("Max Threads", 1, 20, 1) 
            retry_count = st.slider("Auto Retry", 0, 5, 3)
            blur_limit = st.slider("Min Sharpness (Score)", 0.0, 50.0, 5.0, help="Score < 5.0 is typically blurry.")
            st.markdown("---")
            
            st.markdown("#### 📂 Staging Folder (SSD Saver)")
            current_temp = st.session_state.get('temp_folder_path', BASE_WORK_DIR)
            
            if "/mnt/d" in current_temp.lower():
                st.success(f"✅ AMAN: Drive Internal (D:)\n`{os.path.basename(current_temp)}`")
            elif "/mnt/c" in current_temp.lower() or "/mnt/e" in current_temp.lower() or current_temp == BASE_WORK_DIR:
                st.error(f"🔥 BAHAYA: Drive Eksternal (C:/E:)\n`{os.path.basename(current_temp)}`")
                st.caption("Klik 📁 di bawah untuk pindah ke Drive D!")
            else:
                st.warning(f"⚠️ Unknown Drive: `{current_temp}`")

            c_temp1, c_temp2 = st.columns([1, 4])
            with c_temp1:
                st.button("📁", key="btn_temp", on_click=handle_temp_picker, help="Pilih folder di Drive D: agar NVMe Eksternal tidak panas")
            with c_temp2:
                st.text_input("Path", value=current_temp, key="temp_folder_input", label_visibility="collapsed", disabled=True)
            
            st.markdown("---")
            opt_skip = st.checkbox("Skip Processed (Resume)", True)
            opt_rename = st.checkbox("Auto Rename File", True) 
            opt_folder = st.checkbox("Auto Folder Sort", True)
    else:
        opt_skip, opt_rename, opt_folder = True, True, True
        st.info("Settings are available in Metadata or Prompt menu.")

    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
    c_s1, c_s2 = st.columns(2)
    with c_s1: 
        if st.button("🔄 Reload"): st.rerun()
    with c_s2: 
        if st.button("🛑 Stop", type="primary"): 
            st.session_state['watching'] = False 
            st.warning("Stopping..."); time.sleep(1); os.kill(os.getpid(), signal.SIGTERM)

# ================= PAGE: GALLERY (NEW HOME) =================
if selected_menu == "Gallery":
    st.title("🖼️ Smart Gallery")
    
    # 1. Search Bar & Status
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        search_query = st.text_input("🔍 Cari File (Filename / Title)", value=st.session_state['gallery_search'], placeholder="Ketik untuk memfilter...")
        if search_query != st.session_state['gallery_search']:
            st.session_state['gallery_search'] = search_query
            st.session_state['gallery_page'] = 1
            st.rerun()
            
    with col_t2:
        _, total_all = get_paginated_history(page=1, per_page=1, search_query="") 
        st.metric("Total Items", total_all)

    # 2. Pagination Logic
    ITEMS_PER_PAGE = 12
    rows, total_items = get_paginated_history(
        page=st.session_state['gallery_page'], 
        per_page=ITEMS_PER_PAGE, 
        search_query=st.session_state['gallery_search']
    )
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    # ================= BATCH ACTION TOOLBAR =================
    if rows:
        with st.expander("⚡ Batch Actions (Aksi Massal)", expanded=False):
            st.info(f"Opsi ini akan menerapkan perintah Anda ke **{len(rows)} file** yang sedang tampil di halaman ini.")
            
            # Pilihan File (Multiselect) - Default terpilih semua
            # Kita buat dictionary untuk mapping label ke object row
            row_map = {f"{r['new_filename']}": r for r in rows}
            selected_files = st.multiselect("Pilih File yang akan direvisi:", list(row_map.keys()), default=list(row_map.keys()))
            
            batch_instruction = st.text_input("Instruksi Masal", placeholder="Contoh: Tambahkan kata 'High Quality', Hapus keyword 'blur', Ubah judul jadi Bahasa Indonesia")
            
            if st.button(f"🚀 Proses Batch ({len(selected_files)} Files)", type="primary"):
                if not batch_instruction:
                    st.warning("Mohon isi instruksi revisi terlebih dahulu.")
                elif not selected_files:
                    st.warning("Tidak ada file yang dipilih.")
                else:
                    api_key = st.session_state.get('active_api_key_for_correction') or st.session_state.get('active_global_api_key')
                    model = st.session_state.get('active_model_for_correction', 'gemini-1.5-flash')
                    rules = {'title': st.session_state.get('active_title_rule', ''), 'desc': st.session_state.get('active_desc_rule', '')}
                    
                    if not api_key:
                        st.error("API Key belum diset! Cek sidebar.")
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        success_count = 0
                        
                        for i, fname in enumerate(selected_files):
                            row = row_map[fname]
                            full_path = os.path.join(row['output_path'], row['new_filename'])
                            
                            status_text.text(f"Memproses {i+1}/{len(selected_files)}: {fname}...")
                            
                            if os.path.exists(full_path):
                                # Panggil fungsi regenerate
                                suc, res, np = regenerate_metadata_and_rename(full_path, batch_instruction, api_key, model, rules)
                                if suc: success_count += 1
                            else:
                                st.warning(f"File hilang: {fname}")
                                
                            progress_bar.progress((i + 1) / len(selected_files))
                        
                        status_text.empty()
                        progress_bar.empty()
                        st.success(f"Batch Selesai! {success_count} file berhasil diupdate.")
                        time.sleep(1.5)
                        st.rerun()

    st.markdown("---")

    # 3. Grid Display
    if rows:
        cols = st.columns(4) 
        for i, row in enumerate(rows):
            with cols[i % 4]:
                render_minimal_card(row, i)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 4. Pagination Controls
        c_p1, c_p2, c_p3 = st.columns([1, 2, 1])
        with c_p1:
            if st.session_state['gallery_page'] > 1:
                if st.button("⬅️ Previous"):
                    st.session_state['gallery_page'] -= 1
                    st.rerun()
        with c_p2:
            st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Page <b>{st.session_state['gallery_page']}</b> of <b>{total_pages}</b></div>", unsafe_allow_html=True)
        with c_p3:
            if st.session_state['gallery_page'] < total_pages:
                if st.button("Next ➡️"):
                    st.session_state['gallery_page'] += 1
                    st.rerun()
                    
    else:
        st.info("Gallery kosong atau tidak ada hasil pencarian.")
        if st.button("Mulai Proses Metadata Sekarang"): force_navigate(1)

# ================= PAGE: METADATA AUTO =================
elif selected_menu == "Metadata Auto":
    st.title("📸 Metadata Automation")
    
    if not EXIFTOOL_PATH and os.name == 'nt':
        st.error("⚠️ **CRITICAL: ExifTool.exe NOT FOUND!**")
        st.stop()

    with st.container(border=True):
        col_L, col_R = st.columns([1, 1])
        with col_L:
            st.markdown("##### 1. Folder Selection")
            c_i1, c_i2 = st.columns([1, 3])
            with c_i1: 
                st.button("📂 Browse", key="btn_in", on_click=handle_input_picker)
            with c_i2: 
                st.text_input("Source Path", value=st.session_state['selected_folder_path'], key="manual_in_text", on_change=update_manual_input_path, label_visibility="collapsed", placeholder="Paste path here...")
            c_o1, c_o2 = st.columns([1, 3])
            with c_o1: 
                st.button("📂 Output", key="btn_out", on_click=handle_output_picker)
            with c_o2: 
                st.text_input("Dest Path", value=st.session_state['selected_output_path'] or "Default: /output", key="manual_out_text", on_change=update_manual_output_path, label_visibility="collapsed")
        with col_R:
            st.markdown("##### 2. Prompt Style")
            st.selectbox("Style Preset", options=list(PROMPT_PRESETS.keys()), index=list(PROMPT_PRESETS.keys()).index(st.session_state['active_preset_name']), key="preset_selector", on_change=update_preset)
            with st.expander("View Active Prompt Rules", expanded=True): st.info(f"**Title Rule:** {st.session_state['active_title_rule']}")

    ACTIVE_INPUT_DIR = st.session_state['selected_folder_path']
    ACTIVE_OUTPUT_DIR = st.session_state['selected_output_path'] if st.session_state['selected_output_path'] else DEFAULT_INTERNAL_OUTPUT
    CURRENT_TEMP_DIR = st.session_state.get('temp_folder_path', BASE_WORK_DIR)

    tab_manual, tab_watch = st.tabs(["🚀 Manual Process (Batch)", "👁️ Live Monitor (Auto)"])
    
    # --- TAB 1: MANUAL BATCH ---
    with tab_manual:
        local_files = []
        if ACTIVE_INPUT_DIR and os.path.exists(ACTIVE_INPUT_DIR):
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.mp4', '*.mov', '*.avi', '*.eps', '*.ai']:
                local_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext)))
                local_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext.upper())))
            local_files = sorted(list(set(local_files)))
        
        if len(local_files) > 0:
            st.write(f"Found **{len(local_files)}** files ready to process.")
            
            with st.expander("👯 Similarity & Dedup Check (Save Money)", expanded=True):
                c_sim1, c_sim2 = st.columns([2, 1])
                with c_sim1:
                    sim_threshold = st.slider("Similarity Threshold (%)", 80, 100, 95, help="Jika kemiripan > X%, foto dianggap duplikat.")
                with c_sim2:
                    st.write("") 
                    st.caption(f"Strictness: {'Sangat Ketat' if sim_threshold==100 else 'Burst/Varian'}")

                if st.button("🔍 Scan for Duplicates First"):
                    st.session_state['clean_file_list'] = []
                    st.info(f"🔥 Burning CPU: Generating hashes for {len(local_files)} files...")
                    scan_bar = st.progress(0)
                    progress_text = st.empty()
                    results = []
                    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
                        futures = {executor.submit(get_file_hash_wrapper, f): f for f in local_files}
                        for i, future in enumerate(as_completed(futures)):
                            results.append(future.result())
                            scan_bar.progress((i + 1) / len(local_files))
                            if i % 10 == 0: progress_text.text(f"Hashed {i+1}/{len(local_files)}...")
                    
                    st.info("🧠 Analyzing similarities...")
                    results.sort(key=lambda x: x[0])
                    seen_hashes = [] 
                    duplicates_found = []
                    clean_list = []
                    
                    for i, (fpath, h) in enumerate(results):
                        is_dupe = False
                        if h is not None:
                            for seen_h, seen_f in seen_hashes:
                                sim = calculate_similarity_percentage(h, seen_h)
                                if sim >= sim_threshold:
                                    duplicates_found.append((os.path.basename(fpath), os.path.basename(seen_f), sim))
                                    is_dupe = True
                                    break
                        if not is_dupe:
                            if h is not None: seen_hashes.append((h, fpath))
                            clean_list.append(fpath)
                            
                    st.session_state['clean_file_list'] = clean_list
                    scan_bar.empty(); progress_text.empty()

                    if duplicates_found:
                        DUPE_DIR = os.path.join(ACTIVE_INPUT_DIR, "duplicates")
                        if not os.path.exists(DUPE_DIR): os.makedirs(DUPE_DIR)
                        for fname, origin, score in duplicates_found:
                            try: 
                                src = os.path.join(ACTIVE_INPUT_DIR, fname)
                                dst = os.path.join(DUPE_DIR, fname)
                                shutil.move(src, dst)
                            except: pass
                        st.warning(f"Found & Moved {len(duplicates_found)} duplicates to '/duplicates' folder.")
                    else:
                        st.success("No duplicates found! All files are unique.")

            files_to_process_source = st.session_state.get('clean_file_list')
            if not files_to_process_source: files_to_process_source = local_files

            st.markdown("---")
            st.markdown(f"#### Ready to AI Process: **{len(files_to_process_source)}** files")
            
            with st.expander("💰 Final Cost Estimation"):
                input_est, output_est = 558, 200
                curr_price = MODEL_PRICES["default"]
                for k in MODEL_PRICES:
                    if k in final_model_name.lower(): curr_price = MODEL_PRICES[k]; break
                est_cost_unit = ((input_est / 1e6) * curr_price["in"]) + ((output_est / 1e6) * curr_price["out"])
                
                c_lim1, c_lim2 = st.columns(2)
                with c_lim1:
                    if len(files_to_process_source) > 1:
                        files_limit = st.slider("Limit Processing Amount", 1, len(files_to_process_source), len(files_to_process_source))
                    else:
                        st.text_input("Processing Amount", value="1", disabled=True)
                        files_limit = 1
                with c_lim2: st.metric("Estimated Cost", f"${est_cost_unit * files_limit:.4f}")

            counter_col1, counter_col2 = st.columns([1, 3])
            with counter_col1: st.markdown("### 📊 Status")
            with counter_col2:
                status_counter = st.empty()
                status_counter.metric(label="Processed / Total", value=f"0 / {files_limit}")

            if st.button(f"🚀 Start Processing ({files_limit} files)", type="primary", disabled=not active_api_key):
                DONE_DIR = os.path.join(ACTIVE_INPUT_DIR, "done")
                SKIP_DIR = os.path.join(ACTIVE_INPUT_DIR, "skipped") 
                if not os.path.exists(DONE_DIR): os.makedirs(DONE_DIR)
                if not os.path.exists(SKIP_DIR): os.makedirs(SKIP_DIR)
                
                force_save_all_settings()

                start_time_total = time.time()
                prompt_str = construct_prompt_template(st.session_state['active_title_rule'], st.session_state['active_desc_rule'])
                opts = {"rename": opt_rename, "skip_existing": opt_skip, "blur_check": True} 
                base_url = current_provider_config.get("base_url")

                prog_bar = st.progress(0)
                status_area = st.empty()
                log_container = st.container(border=True, height=200)
                
                cnt_ok, cnt_skip, cnt_fail = 0, 0, 0
                data_master, data_adobe, data_getty, data_shutter = [], [], [], []

                def read_proc(fpath):
                    return process_single_file(
                        os.path.basename(fpath), provider_choice, final_model_name, active_api_key, base_url, 
                        retry_count, opts, prompt_str, ACTIVE_INPUT_DIR, 
                        custom_temp_dir=CURRENT_TEMP_DIR,
                        blur_threshold=blur_limit
                    )

                files_to_run = files_to_process_source[:files_limit]
                
                try:
                    with ThreadPoolExecutor(max_workers=num_workers) as exe:
                        futures = {exe.submit(read_proc, fp): fp for fp in files_to_run}
                        
                        for i, fut in enumerate(as_completed(futures)):
                            res = fut.result()
                            elapsed = time.time() - start_time_total
                            processed = i + 1
                            status_counter.metric(label="Processed / Total", value=f"{processed} / {files_limit}")
                            status_area.info(f"⏳ Processing... | Time: {elapsed:.0f}s")
                            
                            with log_container:
                                if res["status"] == "success":
                                    cnt_ok += 1
                                    ftype = res.get('file_type', 'Other')
                                    
                                    if opt_folder: tdir = os.path.join(ACTIVE_OUTPUT_DIR, ftype, res['category'])
                                    else: tdir = os.path.join(ACTIVE_OUTPUT_DIR, ftype)
                                    if not os.path.exists(tdir): os.makedirs(tdir)
                                    
                                    try:
                                        temp_staging_file = os.path.join(CURRENT_TEMP_DIR, res['new_name'])
                                        shutil.copy2(res['original_path'], temp_staging_file)
                                        
                                        item_data = {'SourceFile': temp_staging_file}
                                        item_data.update(res['tags_data'])
                                        flush_metadata_queue([item_data]) 
                                        
                                        final_file_path = os.path.join(tdir, res['new_name'])
                                        shutil.move(temp_staging_file, final_file_path)
                                        
                                        shutil.move(res['original_path'], os.path.join(DONE_DIR, res['file']))
                                        
                                        kw_list = res['tags_data'].get('XMP:Subject', [])
                                        create_xmp_sidecar(os.path.splitext(final_file_path)[0], res['meta_title'], res['meta_desc'], kw_list)

                                        st.success(f"✅ {res['new_name']} ({ftype})")
                                        
                                        rm, ra, rg, rs = prepare_csv_rows(res)
                                        data_master.append(rm); data_adobe.append(ra); data_getty.append(rg); data_shutter.append(rs)
                                        
                                        add_history_entry(res['file'], res['new_name'], res['meta_title'], res['meta_desc'], res['meta_kw'], res['category'], tdir)
                                        
                                    except Exception as e: st.error(f"IO/Move Error: {e}"); cnt_fail += 1
                                elif res["status"] == "skipped":
                                    cnt_skip += 1
                                    try: shutil.move(os.path.join(ACTIVE_INPUT_DIR, res['file']), os.path.join(SKIP_DIR, res['file']))
                                    except: pass
                                    st.warning(f"⚠️ Skipped: {res['file']}")
                                else: 
                                    cnt_fail += 1
                                    st.error(f"❌ Gagal Memproses: {res['file']}")

                            prog_bar.progress(processed / len(files_to_process_source))
                
                finally:
                    pass

                if data_master:
                    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    report_dir = os.path.join(ACTIVE_OUTPUT_DIR, "_Reports")
                    if not os.path.exists(report_dir): os.makedirs(report_dir)
                    pd.DataFrame(data_master).to_csv(os.path.join(report_dir, f"Batch_Master_{ts}.csv"), index=False)
                    st.toast(f"📄 Reports generated in {report_dir}")

                status_area.success(f"🎉 Batch Complete! Success: {cnt_ok}, Skipped: {cnt_skip}, Failed: {cnt_fail}")
        else:
            if ACTIVE_INPUT_DIR: st.info("📁 Folder kosong / tidak ada file baru.")
            else: st.warning("⚠️ Select Input Folder.")

    # --- TAB 2: LIVE MONITOR ---
    with tab_watch:
        st.info("👁️ **Live Monitor**: Supports Photo, Video, Vector. Checks folder every 5s.")
        
        wd_counter = st.empty()
        wd_counter.metric("Session Processed", f"{st.session_state['processed_session_count']} Files")

        current_backlog = []
        if ACTIVE_INPUT_DIR and os.path.exists(ACTIVE_INPUT_DIR):
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.mp4', '*.mov', '*.avi', '*.eps', '*.ai']:
                current_backlog.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext)))
                current_backlog.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext.upper())))
            current_backlog = sorted(list(set(current_backlog)))
        
        col_m1, col_m2 = st.columns([1,4])
        with col_m1:
            if not st.session_state['watching']:
                if st.button("▶️ Start", type="primary", disabled=not (active_api_key and ACTIVE_INPUT_DIR)):
                    st.session_state['watching'] = True
                    st.session_state['processed_session_count'] = 0 
                    st.rerun()
            else:
                if st.button("⏹️ Stop"): 
                    st.session_state['watching'] = False
                    st.rerun()
        with col_m2:
            st.markdown("🟢 **Running**" if st.session_state['watching'] else "🔴 **Stopped**")

        if st.session_state['watching'] and active_api_key and ACTIVE_INPUT_DIR:
            monitor_log = st.empty()
            
            DONE_DIR = os.path.join(ACTIVE_INPUT_DIR, "done")
            SKIP_DIR = os.path.join(ACTIVE_INPUT_DIR, "skipped") 
            if not os.path.exists(DONE_DIR): os.makedirs(DONE_DIR)
            if not os.path.exists(SKIP_DIR): os.makedirs(SKIP_DIR)
            
            prompt_str = construct_prompt_template(st.session_state['active_title_rule'], st.session_state['active_desc_rule'])
            opts = {"rename": opt_rename, "skip_existing": opt_skip, "blur_check": True}
            base_url = current_provider_config.get("base_url")
            
            try:
                while st.session_state['watching']:
                    current_files = []
                    for ext in ['*.jpg', '*.jpeg', '*.png', '*.mp4', '*.mov', '*.avi', '*.eps', '*.ai']:
                        current_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext)))
                        current_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext.upper())))
                    current_files = sorted(list(set(current_files)))

                    if current_files:
                        monitor_log.info(f"🔎 Found {len(current_files)} files. Processing...")
                        for fp in current_files:
                            if not st.session_state['watching']: break 
                            
                            fname = os.path.basename(fp)
                            res = process_single_file(
                                fname, provider_choice, final_model_name, active_api_key, base_url, 
                                retry_count, opts, prompt_str, ACTIVE_INPUT_DIR, 
                                custom_temp_dir=CURRENT_TEMP_DIR, 
                                blur_threshold=blur_limit
                            )
                            st.session_state['processed_session_count'] += 1 
                            wd_counter.metric("Session Processed", f"{st.session_state['processed_session_count']} Files")
                            
                            if res["status"] == "success":
                                ftype = res.get('file_type', 'Other')
                                if opt_folder: tdir = os.path.join(ACTIVE_OUTPUT_DIR, ftype, res['category'])
                                else: tdir = os.path.join(ACTIVE_OUTPUT_DIR, ftype)
                                if not os.path.exists(tdir): os.makedirs(tdir)
                                try:
                                    temp_staging_file = os.path.join(CURRENT_TEMP_DIR, res['new_name'])
                                    shutil.copy2(res['original_path'], temp_staging_file)
                                    
                                    item_data = {'SourceFile': temp_staging_file}
                                    item_data.update(res['tags_data'])
                                    flush_metadata_queue([item_data]) 
                                    
                                    final_file_path = os.path.join(tdir, res['new_name'])
                                    shutil.move(temp_staging_file, final_file_path)
                                    
                                    shutil.move(res['original_path'], os.path.join(DONE_DIR, res['file']))
                                    
                                    kw_list = res['tags_data'].get('XMP:Subject', [])
                                    create_xmp_sidecar(os.path.splitext(final_file_path)[0], res['meta_title'], res['meta_desc'], kw_list)

                                    st.toast(f"✅ Processed: {res['new_name']}")
                                    add_history_entry(res['file'], res['new_name'], res['meta_title'], res['meta_desc'], res['meta_kw'], res['category'], tdir)
                                    
                                except Exception as e: st.error(f"Move Error: {e}")
                            elif res["status"] == "skipped":
                                try: shutil.move(os.path.join(ACTIVE_INPUT_DIR, res['file']), os.path.join(SKIP_DIR, res['file']))
                                except: pass
                                st.toast(f"⚠️ Skipped: {fname}")
                            else: st.toast(f"❌ Failed: {fname}")
                            break 
                        
                        time.sleep(0.1); st.rerun()
                    else:
                        monitor_log.info(f"💤 Waiting... ({datetime.datetime.now().strftime('%H:%M:%S')})")
                        time.sleep(5); st.rerun()
            finally:
                pass 

# ================= PAGE: PROMPT ARCHITECT =================
elif selected_menu == "Prompt Architect":
    st.title("🎨 Prompt Architect")
    st.caption("Generate detailed image prompts for multiple concepts.")
    
    col_p1, col_p2 = st.columns([1, 1])
    
    with col_p1:
        concepts_data = {}
        for i in range(1, 5):
            is_expanded = True if i == 1 else False
            with st.expander(f"✨ Concept {i}", expanded=is_expanded):
                idea_key = f"idea_{i}"; style_key = f"style_{i}"; num_key = f"num_{i}"
                idea_val = st.text_area(f"Describe Concept {i}", height=80, placeholder="e.g. A cat sitting on a neon roof...", key=idea_key)
                
                c_sub1, c_sub2 = st.columns(2)
                with c_sub1: 
                    style_val = st.selectbox(f"Style {i}", ["Photorealistic", "Cinematic", "Minimalist", "3D Render", "Vector Art", "Anime", "Cyberpunk", "Surrealism"], key=style_key)
                with c_sub2: 
                    num_val = st.number_input(f"Count {i}", min_value=1, max_value=50, value=3, step=1, key=num_key)
                
                if idea_val.strip(): 
                    concepts_data[i] = {"idea": idea_val, "style": style_val, "num": num_val}

        st.markdown("---")
        if st.button("Generate All Prompts 🪄", type="primary", disabled=not active_api_key):
            if not concepts_data:
                st.warning("⚠️ Please fill in at least one Concept.")
            else:
                try:
                    genai.configure(api_key=active_api_key)
                    mod = genai.GenerativeModel(final_model_name)
                    
                    st.session_state['prompt_results_text'] = ""
                    progress_text = st.empty()
                    
                    for idx, (c_id, data) in enumerate(concepts_data.items()):
                        progress_text.text(f"Generating Concept {c_id} ({data['style']})...")
                        
                        p = f"""
                        Role: Expert AI Image Prompt Engineer (Midjourney/Stable Diffusion).
                        Task: Write {data['num']} distinct, high-quality image generation prompts for the concept: '{data['idea']}'.
                        Visual Style: {data['style']}.
                        
                        IMPORTANT RULES:
                        1. NO parameter tags (e.g. --ar, --v, --style).
                        2. NO numbering.
                        3. NO introductory text.
                        4. SEPARATE PROMPTS WITH: ||| 
                        5. For Minimalist: describe visual composition/negative space.
                        """
                        
                        res = mod.generate_content(p)
                        clean_res = res.text.replace("*", "").replace("#", "").strip()
                        
                        for tag in ["--ar", "--v", "--style", "--zoom", "--q", "--s"]:
                            clean_res = clean_res.replace(tag, "")
                        
                        raw_prompts = [x.strip() for x in clean_res.split("|||") if x.strip()]
                        
                        st.session_state['prompt_results_text'] += "\n".join(raw_prompts) + "\n\n"
                        
                        add_prompt_history(data['idea'], data['style'], final_model_name, "\n---\n".join(raw_prompts))
                    
                    progress_text.text("Done!")
                    st.toast(f"Success! Generated prompts for {len(concepts_data)} concepts.", icon="✅")
                    
                except Exception as e:
                    st.error(f"Generation Error: {str(e)}")

    with col_p2:
        with st.container(border=True):
            st.markdown("##### 2. Result (Raw Text)")
            st.text_area("Copy all prompts here:", value=st.session_state['prompt_results_text'], height=600, label_visibility="collapsed")

# ================= PAGE: HISTORY =================
elif selected_menu == "History Log":
    st.title("📜 Process History")
    tab_meta, tab_prompt = st.tabs(["📸 Metadata Logs", "🎨 Prompt Logs"])
    
    with tab_meta:
        c_h1, c_h2 = st.columns([5,1])
        with c_h2: 
            if st.button("Trash Metadata", type="primary"): clear_history(); st.rerun()
        df = get_history_df()
        if not df.empty: st.dataframe(df, use_container_width=True, hide_index=True)
        else: st.info("Empty records.")
            
    with tab_prompt:
        c_hp1, c_hp2 = st.columns([5,1])
        with c_hp2: 
            if st.button("Trash Prompts", type="primary"): clear_prompt_history(); st.rerun()
        df_p = get_prompt_history_df()
        if not df_p.empty: st.dataframe(df_p, use_container_width=True, hide_index=True)
        else: st.info("Empty records.")