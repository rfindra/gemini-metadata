# app_helpers.py
import streamlit as st
import os
import json
import shutil
import datetime
import exiftool
import math
import platform
import subprocess
from dotenv import load_dotenv

# Import Config & Modules
from config import BASE_WORK_DIR, EXIFTOOL_PATH, PROMPT_PRESETS, PROVIDERS
from utils import select_folder_from_wsl, construct_prompt_template
from processor import process_single_file
from image_ops import create_xmp_sidecar, compute_dhash
from database import update_history_entry

# Load Env
load_dotenv(override=True)

SETTINGS_FILE = "user_settings.json"

# --- HARDWARE DETECTION (NEW) ---
@st.cache_resource
def get_hardware_status():
    """Mendeteksi Hardware Akselerasi (NVIDIA/AMD/Intel/Apple Silicon)."""
    system = platform.system()
    
    # 1. Cek Apple Silicon (Mac)
    if system == "Darwin":
        machine = platform.machine()
        if "arm" in machine.lower():
            return "🍏 Apple Silicon (M1/M2/M3)", "success"
        return "💻 Intel Mac (CPU)", "warning"

    # 2. Cek NVIDIA (Windows/WSL/Linux)
    # Cara paling akurat untuk cek CUDA support
    try:
        subprocess.check_output("nvidia-smi", shell=True, stderr=subprocess.DEVNULL)
        return "🟢 NVIDIA GPU Detected", "success"
    except:
        pass

    # 3. Cek General GPU (Intel/AMD) via lspci (Linux/WSL)
    if system == "Linux":
        try:
            # Cek device display/vga/3d
            pci_out = subprocess.check_output("lspci | grep -i 'vga\\|3d\\|display'", shell=True, stderr=subprocess.DEVNULL).decode().lower()
            
            if "intel" in pci_out:
                return "🔵 Intel IGP/Arc Detected", "info"
            elif "amd" in pci_out or "ati" in pci_out:
                return "🔴 AMD Radeon GPU Detected", "info"
            elif "microsoft" in pci_out:
                # WSL2 seringkali terbaca sebagai Microsoft Basic Render Driver jika tidak ada passthrough
                return "⚠️ WSL Virtual Device (CPU)", "warning"
        except:
            pass

    # 4. Fallback Windows (wmic) jika bukan WSL
    if system == "Windows":
        try:
            wmic_out = subprocess.check_output("wmic path win32_VideoController get name", shell=True).decode().lower()
            if "intel" in wmic_out: return "🔵 Intel Graphics", "info"
            if "amd" in wmic_out or "radeon" in wmic_out: return "🔴 AMD Radeon", "info"
        except:
            pass

    return "⚠️ CPU Mode (No Dedicated GPU)", "warning"

# --- STATE MANAGEMENT ---
def init_session_state():
    """Inisialisasi semua variabel session state default."""
    defaults = {
        'menu_index': 0,
        'gallery_page': 1,
        'gallery_search': "",
        'watching': False,
        'nav_key': 0,
        'processed_session_count': 0,
        'prompt_results_text': "",
        'clean_file_list': [],
        'active_preset_name': "Commercial (Standard) - BEST SELLER",
        'active_title_rule': PROMPT_PRESETS["Commercial (Standard) - BEST SELLER"]['title'],
        'active_desc_rule': PROMPT_PRESETS["Commercial (Standard) - BEST SELLER"]['desc'],
        'active_global_api_key': "",
        'active_api_key_for_correction': "",
        'active_model_for_correction': ""
    }

    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
    
    # Load settings path
    saved = load_settings()
    if 'temp_folder_path' not in st.session_state:
        st.session_state['temp_folder_path'] = saved.get("temp_folder", BASE_WORK_DIR)
    if 'selected_output_path' not in st.session_state:
        st.session_state['selected_output_path'] = saved.get("output_folder", "")
    if 'selected_folder_path' not in st.session_state:
        st.session_state['selected_folder_path'] = ""

    # Load Global API Key from Env if available
    default_provider = "Google Gemini (Native)"
    try:
        env_var = PROVIDERS[default_provider]["env_var"]
        env_key = os.getenv(env_var)
        if env_key and not st.session_state['active_global_api_key']:
            st.session_state['active_global_api_key'] = env_key
    except: pass

# --- SETTINGS HANDLERS ---
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_settings(key, value):
    settings = load_settings()
    settings[key] = value
    with open(SETTINGS_FILE, "w") as f: json.dump(settings, f)

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

def handle_input_picker():
    path = select_folder_from_wsl("Pilih Folder SUMBER (Drive D:)")
    if path: st.session_state['selected_folder_path'] = path

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

def force_navigate(index):
    st.session_state['menu_index'] = index
    st.session_state['nav_key'] += 1 
    st.rerun()

# --- BUSINESS LOGIC HELPERS ---

def get_file_hash_wrapper(fpath):
    try: return fpath, compute_dhash(fpath)
    except: return fpath, None

def flush_metadata_queue(queue_list):
    if not queue_list: return
    et_path = EXIFTOOL_PATH 
    if not et_path and os.name != 'nt': et_path = "exiftool"
    try:
        with exiftool.ExifToolHelper(executable=et_path) as et:
            for item in queue_list:
                src_file = item.pop('SourceFile') 
                try: et.set_tags(src_file, tags=item, params=["-overwrite_original", "-codedcharacterset=utf8", "-sep", ", "])
                except Exception as e: print(f"Meta error {src_file}: {e}")
    except Exception as e: print(f"Exiftool error: {e}")

def prepare_csv_rows(res):
    today = datetime.date.today().strftime("%Y-%m-%d")
    now = datetime.datetime.now().strftime("%H:%M:%S")
    is_ill = "Yes" if res.get('file_type') == "Vector" else "No"
    
    rm = {"Filename": res['new_name'], "Original": res['file'], "Title": res['meta_title'], "Description": res['meta_desc'], "Keywords": res['meta_kw'], "Category": res['category'], "Type": res.get('file_type'), "Date": today, "Time": now, "Releases": "", "Country": "", "Editorial": "No", "Mature Content": "No", "Illustration": is_ill}
    ra = {"Filename": res['new_name'], "Title": res['meta_title'], "Keywords": res['meta_kw'], "Category": res['category'], "Releases": ""}
    rg = {"file name": res['new_name'], "created date": today, "description": res['meta_desc'], "country": "", "brief code": "", "title": res['meta_title'], "keywords": res['meta_kw']}
    rs = {"Filename": res['new_name'], "Description": res['meta_desc'], "Keywords": res['meta_kw'], "Categories": res['category'], "Editorial": "No", "Mature content": "No", "illustration": is_ill}
    return rm, ra, rg, rs

def regenerate_metadata_and_rename(file_path, correction_prompt, api_key, model_name, active_rules):
    try:
        source_dir = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        
        # Setup Processor
        provider = "Google Gemini (Native)"
        base_prompt = construct_prompt_template(active_rules['title'], active_rules['desc'])
        opts = {"rename": True, "blur_check": False} 

        # AI Process
        res = process_single_file(
            filename=filename, provider=provider, model=model_name, api_key=api_key, base_url=None, max_retries=1,
            options=opts, full_prompt=base_prompt, source_dir=source_dir,
            custom_temp_dir=st.session_state.get('temp_folder_path', BASE_WORK_DIR), blur_threshold=0.0,
            user_correction=correction_prompt 
        )

        if res['status'] == 'error': return False, f"AI Error: {res['msg']}", None
        
        # Write Metadata
        et_path = EXIFTOOL_PATH if EXIFTOOL_PATH else ("exiftool" if os.name!='nt' else None)
        with exiftool.ExifToolHelper(executable=et_path) as et:
            et.set_tags(file_path, tags=res['tags_data'], params=["-overwrite_original", "-codedcharacterset=utf8", "-sep", ", "])

        # Rename File
        new_filename = res['new_name']
        new_file_path = os.path.join(source_dir, new_filename)
        if filename != new_filename:
            try:
                shutil.move(file_path, new_file_path)
                old_xmp = os.path.splitext(file_path)[0] + ".xmp"
                if os.path.exists(old_xmp): os.remove(old_xmp)
            except Exception as e:
                print(f"Rename failed: {e}"); new_file_path = file_path

        # Create Sidecar
        kw_list = res['tags_data'].get('XMP:Subject', [])
        create_xmp_sidecar(os.path.splitext(new_file_path)[0], res['meta_title'], res['meta_desc'], kw_list)
        
        # Update DB
        update_history_entry(old_filename_in_db=filename, new_filename=new_filename, title=res['meta_title'], desc=res['meta_desc'], keywords=res['meta_kw'])
        
        return True, {"title": res['meta_title'], "desc": res['meta_desc'], "kw": kw_list}, new_file_path
        
    except Exception as e: return False, str(e), None