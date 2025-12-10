import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import json
import re
import io
import time
import os
import signal
import glob
import datetime
import exiftool
import cv2
import subprocess
import pandas as pd
import shutil
import base64
import sqlite3
from PIL import Image, ImageStat
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= KONFIGURASI DATABASE =================
DB_FILE = "gemini_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            filename TEXT,
            new_filename TEXT,
            title TEXT,
            description TEXT,
            keywords TEXT,
            category TEXT,
            output_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_history_entry(filename, new_filename, title, desc, keywords, category, output_path):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO history (timestamp, filename, new_filename, title, description, keywords, category, output_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ts, filename, new_filename, title, desc, keywords, category, output_path))
    conn.commit()
    conn.close()

def get_history_df():
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query("SELECT * FROM history ORDER BY id DESC", conn)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def clear_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()

init_db()

# ================= PRICING DATABASE (DYNAMIC) =================
# Harga per 1 Juta Token (Estimasi USD) - Update sesuai provider
MODEL_PRICES = {
    # Google
    "gemini-2.5-flash": {"in": 0.075, "out": 0.30},
    "gemini-2.5-flash-lite": {"in": 0.0375, "out": 0.15},
    "gemma-3-27b": {"in": 0.20, "out": 0.20}, # Est. OpenRouter
    "gemma-3-12b": {"in": 0.10, "out": 0.10},
    
    # OpenAI / Others (jika pakai OpenRouter)
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "claude-3-haiku": {"in": 0.25, "out": 1.25},
    "sonar": {"in": 1.0, "out": 1.0}, # Perplexity
    
    # Fallback Default
    "default": {"in": 0.10, "out": 0.40}
}

def calculate_cost(model_name, tokens_in, tokens_out):
    """Menghitung biaya berdasarkan model ID"""
    price = MODEL_PRICES["default"]
    # Cari harga yang cocok (partial match)
    for key in MODEL_PRICES:
        if key in model_name.lower():
            price = MODEL_PRICES[key]
            break
            
    cost = (tokens_in / 1_000_000 * price["in"]) + (tokens_out / 1_000_000 * price["out"])
    return cost

# ================= FUNGSI KHUSUS WSL (MAGIC FOLDER PICKER) =================
def select_folder_from_wsl(dialog_title="Pilih Folder"):
    try:
        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        $f = New-Object System.Windows.Forms.FolderBrowserDialog
        $f.Description = '{dialog_title}'
        $f.ShowNewFolderButton = $true
        if ($f.ShowDialog() -eq 'OK') {{
            Write-Output $f.SelectedPath
        }}
        """
        cmd = ["powershell.exe", "-Command", ps_script]
        windows_path = subprocess.check_output(cmd).decode().strip()
        if not windows_path: return None
        windows_path = windows_path.strip()
        drive_letter = windows_path[0].lower()
        path_tail = windows_path[2:].replace("\\", "/")
        wsl_path = f"/mnt/{drive_letter}{path_tail}"
        return wsl_path
    except Exception as e:
        return None

# ================= KONFIGURASI PATH DEFAULT =================
BASE_WORK_DIR = os.getcwd()
DEFAULT_INTERNAL_OUTPUT = os.path.join(BASE_WORK_DIR, "output")
if not os.path.exists(DEFAULT_INTERNAL_OUTPUT):
    try: os.makedirs(DEFAULT_INTERNAL_OUTPUT)
    except: pass

# ================= KONFIGURASI HALAMAN =================
st.set_page_config(
    page_title="Gemini Metadata Studio", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ================= PRESET GAYA =================
PROMPT_PRESETS = {
    "Commercial (Standard) - BEST SELLER": {
        "title": "Commercial Style: Subject + Action + Context. Max 30 words. Clear, descriptive, and SEO-friendly.",
        "desc": "Visual Style: Lighting + Composition + Mood. Max 30 words. Professional tone, suitable for advertising."
    },
    "Editorial (News/Journalism)": {
        "title": "Editorial Style: Subject + Action + Location. Max 30 words. Strictly Factual. No opinions.",
        "desc": "Journalistic Description: Who, What, Where, When. Describe the scene objectively. No creative fluff."
    },
    "Creative / Abstract / Backgrounds": {
        "title": "Creative Style: Concept + Metaphor + Key Elements. Evocative language.",
        "desc": "Conceptual Description: Focus on Mood, Textures, Colors, Patterns, and Emotions. Artistic tone."
    },
    "Technical / Minimalist (Isolated)": {
        "title": "Punchy Style: Main Object + Main Characteristic. Max 15 words. Direct.",
        "desc": "Technical Description: Focus on isolation, white background details, and specific angles. Very brief."
    }
}

def construct_prompt_template(title_rule, desc_rule):
    return f"""
    Analyze for Commercial Stock (Photo/Video/Vector). Return strictly JSON.
    SYSTEM CONTEXT (Visual Facts): {{context_injection}}
    Structure: 
    {{
        "title": "{title_rule}", 
        "description": "{desc_rule}", 
        "keywords": "comma separated string of 50 keywords",
        "category": "Pick ONE: People, Nature, Business, Food, Travel, Architecture, Animals, Lifestyle, Technology, Abstract"
    }}
    INSTRUCTIONS:
    1. Title: Focus on WHAT is happening. Must be under 200 characters.
    2. Description: Focus on HOW it looks (aesthetic/technical). Must be under 200 characters.
    3. Keywords: Start with VISIBLE OBJECTS, then CONCEPTS. Include 'no people' if applicable.
    4. No markdown. Only JSON.
    """

# ================= PROVIDER DATA (DEFAULT: GEMMA 3) =================
PROVIDERS = {
    "Google Gemini (Native)": {
        "base_url": None,
        "models": {
            # Urutan diubah agar Gemma 3 jadi default
            "Gemma 3 - 27B (High Intelligence)": "gemma-3-27b-it", 
            "Gemma 3 - 12B (Balanced)": "gemma-3-12b-it",
            "Gemini 2.5 Flash (New Standard)": "gemini-2.5-flash",
            "Gemini 2.5 Flash Lite (Efficiency)": "gemini-2.5-flash-lite",
        }
    },
    "OpenAI / OpenRouter / Perplexity": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": {
            "Auto Detect (Type Manual ID below)": "manual-entry"
        }
    }
}

# ================= CLASS OPTIMIZER HYBRID =================
class StockPhotoOptimizer:
    def __init__(self):
        self.universal_blacklist = {
            "vector", "illustration", "drawing", "painting", 
            "generated", "ai generated", "render", "3d", "artwork", 
            "graphic", "clipart", "cartoon", "sketch", "digital art"
        }
        self.high_value_tech_tags = {"no people", "isolated", "white background", "copy space"}

    def analyze_technical_specs(self, image_path):
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                specs = {"tags": [], "context_str": ""}
                if width > height: specs["tags"].append("horizontal")
                elif height > width: specs["tags"].append("vertical")
                else: specs["tags"].append("square")
                
                if img.mode != 'RGB': img = img.convert('RGB')
                grayscale = img.convert("L")
                stat = ImageStat.Stat(grayscale)
                avg_brightness = stat.mean[0]

                if avg_brightness > 230:
                    specs["tags"].extend(["white background", "isolated", "high key"])
                    specs["context_str"] += " Note: The image has a clean white background, suitable for isolation."
                elif avg_brightness < 40:
                    specs["tags"].extend(["black background", "low key", "dark"])
                    specs["context_str"] += " Note: The image is low-key / dark."
                return specs
        except:
            return {"tags": [], "context_str": ""}

    def clean_and_optimize_tags(self, ai_keywords, technical_tags):
        if isinstance(ai_keywords, list): 
            ai_tokens = [str(t).strip().lower() for t in ai_keywords]
        else: 
            ai_tokens = [t.strip().lower() for t in (ai_keywords or "").split(",")]
        
        tech_tokens = [t.strip().lower() for t in technical_tags]
        seen = {}
        final_ordered_list = []

        def is_valid(t):
            t_clean = re.sub(r"[^a-z0-9\s-]", "", t).strip()
            if len(t_clean) < 2: return False
            if t_clean in self.universal_blacklist: return False
            if t_clean in {"photo", "image", "stock", "hd", "4k"}: return False
            return True

        for t in ai_tokens[:5]:
            if is_valid(t) and t not in seen:
                final_ordered_list.append(t)
                seen[t] = True
        for t in tech_tokens:
            if t in self.high_value_tech_tags and t not in seen:
                final_ordered_list.append(t)
                seen[t] = True
        for t in ai_tokens[5:]:
            if is_valid(t) and t not in seen:
                final_ordered_list.append(t)
                seen[t] = True
        for t in tech_tokens:
            if t not in seen and is_valid(t):
                final_ordered_list.append(t)
                seen[t] = True

        return final_ordered_list[:49]

# ================= FUNGSI UTILS & AI =================
def clean_filename(title):
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    clean = clean.replace(" ", "-").strip().lower()
    return clean[:50]

def extract_json(text):
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.MULTILINE)
    try: return json.loads(cleaned)
    except:
        start = cleaned.find("{")
        if start != -1:
            depth = 0
            for i, c in enumerate(cleaned[start:], start=start):
                if c == "{": depth += 1
                elif c == "}": depth -= 1
                if depth == 0:
                    try: return json.loads(cleaned[start:i+1])
                    except: continue
    return {}

def create_xmp_sidecar(path_without_ext, title, desc, keywords):
    try:
        rdf_keywords = "\n".join([f"<rdf:li>{k}</rdf:li>" for k in keywords])
        xmp_content = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description rdf:about=''
      xmlns:dc='http://purl.org/dc/elements/1.1/'>
      <dc:title>
        <rdf:Alt>
          <rdf:li xml:lang='x-default'>{title}</rdf:li>
        </rdf:Alt>
      </dc:title>
      <dc:description>
        <rdf:Alt>
          <rdf:li xml:lang='x-default'>{desc}</rdf:li>
        </rdf:Alt>
      </dc:description>
      <dc:subject>
        <rdf:Bag>
          {rdf_keywords}
        </rdf:Bag>
      </dc:subject>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""
        xmp_path = f"{path_without_ext}.xmp"
        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(xmp_content)
        return xmp_path
    except:
        return None

def run_gemini_engine(model_name, api_key, image_path, prompt):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    try:
        img = Image.open(image_path)
        response = model.generate_content([prompt, img])
        return extract_json(response.text)
    except Exception as e: raise e

def run_openai_compatible_engine(model_name, api_key, base_url, image_path, prompt):
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        ],
        max_tokens=1000,
    )
    return extract_json(response.choices[0].message.content)

def get_analysis_image_path(original_file_path):
    ext = os.path.splitext(original_file_path)[1].lower()
    temp_img_path = original_file_path + "_preview.jpg"
    if ext in ['.mp4', '.mov', '.avi', '.mkv']:
        try:
            cap = cv2.VideoCapture(original_file_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames > 0: cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2) 
            else: cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(temp_img_path, frame)
                return temp_img_path
            return None
        except: return None
    elif ext in ['.eps', '.ai']:
        try:
            args = ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=jpeg", "-dEPSCrop", "-r150", f"-sOutputFile={temp_img_path}", original_file_path]
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_img_path): return temp_img_path
            return None
        except: return None
    else: return original_file_path

# ================= WORKER PROCESS =================
def process_single_file(filename, provider_type, model_name, api_key, base_url, max_retries, options, full_prompt_string, source_dir):
    thread_id = str(time.time()).replace('.', '')
    
    source_full_path = os.path.join(source_dir, filename)
    temp_file_name = f"temp_{thread_id}_{filename}"
    working_path = os.path.join(BASE_WORK_DIR, temp_file_name)
    
    preview_path = None
    preview_bytes = None
    optimizer = StockPhotoOptimizer()
    
    try:
        shutil.copy2(source_full_path, working_path)
        preview_path = get_analysis_image_path(working_path)
        if not preview_path: raise ValueError("Gagal ekstrak visual file.")
        
        try:
            with open(preview_path, "rb") as fimg:
                preview_bytes = fimg.read()
        except: pass

        tech_specs = optimizer.analyze_technical_specs(preview_path)
        context_injection = tech_specs['context_str']
        prompt = full_prompt_string.replace("{context_injection}", context_injection)
        
        response_data = None
        last_error = ""
        for attempt in range(max_retries):
            try:
                if attempt > 0: time.sleep(2 * attempt)
                if provider_type == "Google Gemini (Native)":
                    response_data = run_gemini_engine(model_name, api_key, preview_path, prompt)
                else:
                    response_data = run_openai_compatible_engine(model_name, api_key, base_url, preview_path, prompt)
                if not response_data: raise ValueError("Empty JSON")
                break 
            except Exception as e:
                last_error = str(e)
                if "429" in str(e) or "quota" in str(e).lower(): time.sleep(15 + (attempt * 5))
                else: time.sleep(1)
        
        if not response_data:
            return {"status": "error", "file": filename, "msg": f"AI Fail: {last_error}"}

        raw_kw = response_data.get("keywords", "")
        kw = optimizer.clean_and_optimize_tags(raw_kw, tech_specs["tags"])
        title = response_data.get("title", "")[:200]
        desc = response_data.get("description", "")[:200]
        category = response_data.get("category", "Uncategorized")
        
        ext = os.path.splitext(filename)[1].lower()
        tags_to_write = {}
        tags_to_write["XMP:Title"] = title
        tags_to_write["XMP:Description"] = desc
        tags_to_write["XMP:Subject"] = kw
        if ext in ['.jpg', '.jpeg', '.png', '.tiff']:
            tags_to_write.update({
                "IPTC:Headline": title, "IPTC:Caption-Abstract": desc, "IPTC:Keywords": kw,
                "EXIF:XPTitle": title, "EXIF:XPKeywords": ";".join(kw), "EXIF:ImageDescription": desc
            })
        elif ext in ['.eps', '.ai']:
             tags_to_write.update({ "IPTC:Headline": title, "IPTC:Keywords": kw })
        
        with exiftool.ExifToolHelper() as et:
            et.set_tags(working_path, tags=tags_to_write, params=["-overwrite_original", "-codedcharacterset=utf8"])

        temp_xmp_path = create_xmp_sidecar(os.path.splitext(working_path)[0], title, desc, kw)
        
        final_name = filename
        if options["rename"]:
            safe_title = clean_filename(title)
            final_name = f"{safe_title}{ext}"
        
        # Token Estimation (Standard Heuristic for Stock Metadata)
        est_input_tokens = 258 + 300 
        est_output_tokens = 200
        
        return {
            "status": "success", 
            "file": filename, 
            "new_name": final_name, 
            "category": category, 
            "temp_result_path": working_path, 
            "temp_xmp_path": temp_xmp_path, 
            "meta_title": title, 
            "meta_desc": desc, 
            "meta_kw": ", ".join(kw),
            "preview_bytes": preview_bytes, 
            "tokens_in": est_input_tokens,
            "tokens_out": est_output_tokens
        }
        
    except Exception as e:
        if os.path.exists(working_path): 
            try: os.remove(working_path)
            except: pass
        return {"status": "error", "file": filename, "msg": f"Sys Error: {str(e)}"}
        
    finally:
        if preview_path and preview_path != working_path and os.path.exists(preview_path): 
            os.remove(preview_path)

# ================= UI FRONTEND & STATE =================

# 1. Init State
DEFAULT_PRESET_KEY = "Commercial (Standard) - BEST SELLER"
if 'active_preset_name' not in st.session_state:
    st.session_state['active_preset_name'] = DEFAULT_PRESET_KEY
    st.session_state['active_title_rule'] = PROMPT_PRESETS[DEFAULT_PRESET_KEY]['title']
    st.session_state['active_desc_rule'] = PROMPT_PRESETS[DEFAULT_PRESET_KEY]['desc']

# 2. Navigation State
MENU_HOME = "Home"
MENU_METADATA = "Metadata Automation"
MENU_PROMPT = "Prompt Architect"
MENU_HISTORY = "History Log"

if 'nav_selection' not in st.session_state:
    st.session_state['nav_selection'] = MENU_HOME

# 3. Input & Output Path State
if 'selected_folder_path' not in st.session_state:
    st.session_state['selected_folder_path'] = ""
if 'selected_output_path' not in st.session_state:
    st.session_state['selected_output_path'] = ""

def go_to_metadata(): st.session_state['nav_selection'] = MENU_METADATA
def go_to_prompt(): st.session_state['nav_selection'] = MENU_PROMPT
def update_preset():
    selected = st.session_state.preset_selector
    st.session_state['active_preset_name'] = selected
    st.session_state['active_title_rule'] = PROMPT_PRESETS[selected]['title']
    st.session_state['active_desc_rule'] = PROMPT_PRESETS[selected]['desc']
    st.toast(f"Style changed to: {selected}")

def handle_input_picker():
    path = select_folder_from_wsl("Pilih Folder SUMBER (Input) Foto/Video")
    if path:
        st.session_state['selected_folder_path'] = path
        st.toast(f"Input Selected: {path}")

def handle_output_picker():
    path = select_folder_from_wsl("Pilih Folder TUJUAN (Output) Hasil")
    if path:
        st.session_state['selected_output_path'] = path
        st.toast(f"Output Selected: {path}")

# --- SIDEBAR ---
with st.sidebar:
    st.title("Navigation")
    selected_menu = st.radio("Go to:", [MENU_HOME, MENU_METADATA, MENU_PROMPT, MENU_HISTORY], key="nav_selection")
    st.divider()
    
    if selected_menu != MENU_HOME and selected_menu != MENU_HISTORY:
        with st.expander("AI Configuration", expanded=True):
            provider_choice = st.selectbox("AI Provider", list(PROVIDERS.keys()), index=0)
            current_provider_config = PROVIDERS[provider_choice]
            model_label = st.selectbox("AI Model", list(current_provider_config["models"].keys()))
            final_model_name = current_provider_config["models"][model_label]
            api_key = st.text_input(f"API Key", type="password")
            if st.checkbox("Custom ID"): final_model_name = st.text_input("Enter ID:", value=final_model_name)

        if selected_menu == MENU_METADATA:
            with st.expander("Process Settings", expanded=True):
                num_workers = st.slider("Worker Threads", 1, 10, 1)
                # [DEFAULT UPDATE] Auto-Rename = True
                opt_rename = st.checkbox("Auto-Rename File", True) 
                opt_folder = st.checkbox("Auto-Folder Category", True)

    st.divider()
    st.caption("System Controls")
    col_sys1, col_sys2 = st.columns(2)
    with col_sys1:
        if st.button("🔄 Rerun", help="Reload App", use_container_width=True):
            st.rerun()
    with col_sys2:
        if st.button("🛑 Stop App", type="primary", help="Shutdown Server", use_container_width=True):
            st.warning("Stopping server...")
            time.sleep(1)
            os.kill(os.getpid(), signal.SIGTERM)

# ================= PAGE: HOME =================
if selected_menu == MENU_HOME:
    st.title("Gemini Metadata Studio")
    st.write("Select a tool to begin:")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Metadata Automation")
            st.write("Auto-tag photos/videos in batch from local folder.")
            st.button("Launch Metadata Studio", type="primary", use_container_width=True, on_click=go_to_metadata)
    with c2:
        with st.container(border=True):
            st.subheader("Prompt Architect")
            st.write("Generate detailed AI prompts from ideas.")
            st.button("Launch Prompt Builder", use_container_width=True, on_click=go_to_prompt)

# ================= PAGE: METADATA =================
elif selected_menu == MENU_METADATA:
    st.subheader("Metadata Automation")
    
    with st.container(border=True):
        c_sel, c_stat = st.columns([3, 1])
        with c_sel:
            st.selectbox("Metadata Style:", options=list(PROMPT_PRESETS.keys()), index=list(PROMPT_PRESETS.keys()).index(st.session_state['active_preset_name']), key="preset_selector", on_change=update_preset)
            with st.expander("View Instructions"):
                st.text_area("Title", value=st.session_state['active_title_rule'], disabled=True, height=70)
                st.text_area("Desc", value=st.session_state['active_desc_rule'], disabled=True, height=70)
        with c_stat:
            st.write("")
            if api_key: st.success("System Ready")
            else: st.error("API Key Needed")

    st.divider()
    
    st.markdown("### 1. Source (Input)")
    col_in_btn, col_in_path = st.columns([1, 4])
    with col_in_btn:
        st.button("📂 Browse Input", on_click=handle_input_picker, use_container_width=True)
    with col_in_path:
        st.text_input("Input Path", value=st.session_state['selected_folder_path'], disabled=True, label_visibility="collapsed", placeholder="Select source folder...")

    st.markdown("### 2. Destination (Output)")
    col_out_btn, col_out_path = st.columns([1, 4])
    with col_out_btn:
        st.button("💾 Browse Output", on_click=handle_output_picker, use_container_width=True)
    with col_out_path:
        st.text_input("Output Path", value=st.session_state['selected_output_path'], disabled=True, label_visibility="collapsed", placeholder="Select destination folder (Optional, default: internal)")

    ACTIVE_INPUT_DIR = st.session_state['selected_folder_path']
    
    if st.session_state['selected_output_path']:
        ACTIVE_OUTPUT_DIR = st.session_state['selected_output_path']
        output_msg = f"Saving to: `{ACTIVE_OUTPUT_DIR}`"
    else:
        ACTIVE_OUTPUT_DIR = DEFAULT_INTERNAL_OUTPUT
        output_msg = f"Saving to: `Default Internal Folder`"

    local_files = []
    
    if ACTIVE_INPUT_DIR and os.path.exists(ACTIVE_INPUT_DIR):
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.mp4', '*.mov', '*.avi', '*.eps', '*.ai']:
            local_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext)))
            local_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext.upper())))
        local_files = sorted(list(set(local_files)))
        
        st.info(f"**{len(local_files)} File(s)** found in Input. | {output_msg}")
        
        # --- [NEW] COST PREVIEW & LIMITER SECTION ---
        if len(local_files) > 0:
            st.divider()
            st.markdown("### 📊 Estimasi & Limit (Anti Boncos)")
            
            # Smart Estimation based on Selected Model
            # Input: Image ~258 + Text ~300 = ~558 tokens. Output ~200 tokens.
            input_est_unit = 558
            output_est_unit = 200
            
            # Cek harga model yang aktif
            # Secara default pakai harga fallback jika tidak ketemu
            current_pricing = MODEL_PRICES["default"]
            model_key_found = False
            for k in MODEL_PRICES:
                if k in final_model_name.lower():
                    current_pricing = MODEL_PRICES[k]
                    model_key_found = True
                    break
            
            est_cost_per_file = ((input_est_unit / 1_000_000) * current_pricing["in"]) + ((output_est_unit / 1_000_000) * current_pricing["out"])
            
            col_calc1, col_calc2 = st.columns(2)
            with col_calc1:
                files_limit = st.slider("Berapa file yang ingin diproses?", 1, len(local_files), len(local_files))
            
            with col_calc2:
                total_est_cost = est_cost_per_file * files_limit
                model_display = f"{final_model_name}" if model_key_found else f"{final_model_name} (Using Default Rate)"
                st.metric(f"Estimasi Biaya ({model_display})", f"${total_est_cost:.5f}")

            files_to_process = local_files[:files_limit]
            
            ready = len(files_to_process) > 0 and api_key
            if st.button(f"Start Process ({len(files_to_process)} Files)", type="primary", disabled=not ready):
                log_cont = st.container(height=400, border=True)
                log_cont.empty()
                st.toast("Processing...")
                
                c1, c2, c3 = st.columns(3)
                with c1: stat_success = st.metric("Success", "0")
                with c2: stat_fail = st.metric("Fail", "0")
                with c3: st.metric("Target", str(len(files_to_process)))
                
                c_cost1, c_cost2 = st.columns(2)
                with c_cost1: metric_tokens = st.empty()
                with c_cost2: metric_dollar = st.empty()
                
                count_ok = 0
                count_err = 0
                total_tokens_in = 0
                total_tokens_out = 0
                
                csv_data = []
                gallery_images = []
                
                opts = {"rename": opt_rename}
                base_url = current_provider_config.get("base_url")
                prog_bar = st.progress(0)
                
                prompt_str = construct_prompt_template(st.session_state['active_title_rule'], st.session_state['active_desc_rule'])
                
                def read_proc(fpath):
                    fname = os.path.basename(fpath)
                    try:
                        return process_single_file(fname, provider_choice, final_model_name, api_key, base_url, 3, opts, prompt_str, ACTIVE_INPUT_DIR)
                    except Exception as e: return {"status": "error", "file": fname, "msg": str(e)}

                with ThreadPoolExecutor(max_workers=num_workers) as exe:
                    futures = {exe.submit(read_proc, fp): fp for fp in files_to_process}
                    for i, fut in enumerate(as_completed(futures)):
                        res = fut.result()
                        with log_cont:
                            if res["status"] == "success":
                                count_ok += 1
                                cat = res['category']
                                fname = res['new_name']
                                temp_path = res['temp_result_path']
                                temp_xmp = res['temp_xmp_path']
                                
                                # Real Cost Calculation
                                t_in = res.get("tokens_in", 0)
                                t_out = res.get("tokens_out", 0)
                                total_tokens_in += t_in
                                total_tokens_out += t_out
                                
                                # Hitung biaya real-time
                                real_cost = calculate_cost(final_model_name, total_tokens_in, total_tokens_out)
                                
                                metric_tokens.metric("Total Tokens", f"{total_tokens_in + total_tokens_out:,}")
                                metric_dollar.metric("Real Cost ($)", f"${real_cost:.4f}")

                                csv_data.append({
                                    "Original Name": res['file'], "New Filename": fname,
                                    "Title": res['meta_title'], "Description": res['meta_desc'],
                                    "Keywords": res['meta_kw'], "Category": cat
                                })
                                
                                if res.get('preview_bytes'):
                                    gallery_images.append((fname, res['preview_bytes']))
                                
                                tdir = os.path.join(ACTIVE_OUTPUT_DIR, cat) if opt_folder else ACTIVE_OUTPUT_DIR
                                if not os.path.exists(tdir): os.makedirs(tdir)
                                final_file_path = os.path.join(tdir, fname)
                                
                                try:
                                    shutil.move(temp_path, final_file_path)
                                    if temp_xmp and os.path.exists(temp_xmp):
                                        final_xmp_name = os.path.splitext(fname)[0] + ".xmp"
                                        shutil.move(temp_xmp, os.path.join(tdir, final_xmp_name))
                                        
                                    st.markdown(f"✅ `{res['file']}` -> `{cat}/{fname}` (+XMP)")
                                    add_history_entry(res['file'], fname, res['meta_title'], res['meta_desc'], res['meta_kw'], cat, final_file_path)
                                except Exception as e:
                                    st.error(f"Move Error: {e}")
                            else:
                                count_err += 1
                                st.markdown(f"❌ `{res['file']}`: {res['msg']}")
                        prog_bar.progress((i+1)/len(files_to_process))
                        stat_success.metric("Success", count_ok)
                        stat_fail.metric("Fail", count_err)
                
                st.success("Batch Complete.")
                
                if gallery_images:
                    with st.expander("✨ Processed Gallery (Preview)", expanded=True):
                        cols = st.columns(4)
                        for idx, (img_name, img_bytes) in enumerate(gallery_images):
                            with cols[idx % 4]:
                                st.image(img_bytes, caption=img_name, use_container_width=True)

                if csv_data:
                    df = pd.DataFrame(csv_data)
                    csv_dir = os.path.join(ACTIVE_OUTPUT_DIR, "csv_reports")
                    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    
                    os.makedirs(os.path.join(csv_dir, "Master_Database"), exist_ok=True)
                    df.to_csv(os.path.join(csv_dir, "Master_Database", f"master_{ts}.csv"), index=False)
                    
                    os.makedirs(os.path.join(csv_dir, "Adobe"), exist_ok=True)
                    dfa = pd.DataFrame({'Filename': df['New Filename'], 'Title': df['Title'], 'Keywords': df['Keywords'], 'Category': df['Category'], 'Releases': ''})
                    dfa.to_csv(os.path.join(csv_dir, "Adobe", f"adobe_{ts}.csv"), index=False)
                    
                    os.makedirs(os.path.join(csv_dir, "Shutterstock"), exist_ok=True)
                    dfs = pd.DataFrame({'Filename': df['New Filename'], 'Description': df['Description'], 'Keywords': df['Keywords'], 'Categories': df['Category'], 'Editorial': 'No', 'Mature content': 'No', 'illustration': 'No'})
                    dfs.to_csv(os.path.join(csv_dir, "Shutterstock", f"ss_{ts}.csv"), index=False)
                    
                    os.makedirs(os.path.join(csv_dir, "Getty"), exist_ok=True)
                    dfg = pd.DataFrame({'file name': df['New Filename'], 'title': df['Title'], 'description': df['Description'], 'keywords': df['Keywords'], 'country': 'Indonesia', 'brief code': '', 'created date': ''})
                    dfg.to_csv(os.path.join(csv_dir, "Getty", f"getty_{ts}.csv"), index=False)
                    
                    st.balloons()
                    st.info(f"All reports saved in: `{csv_dir}`")

    elif ACTIVE_INPUT_DIR:
        st.warning("Input folder invalid/empty.")
    else:
        st.info("Start by selecting an Input Folder.")

# ================= PAGE: PROMPT =================
elif selected_menu == MENU_PROMPT:
    st.subheader("Prompt Architect")
    c1, c2 = st.columns(2)
    with c1:
        idea = st.text_area("Idea:", height=150)
        style = st.selectbox("Style:", ["Photorealistic", "3D Render", "Vector", "Cinematic", "Macro"])
        if st.button("Generate", type="primary", disabled=not api_key):
            if not idea: st.warning("Input idea.")
            else:
                try:
                    genai.configure(api_key=api_key)
                    mod = genai.GenerativeModel(final_model_name)
                    p = f"Role: Expert AI Prompt Engineer. Task: 5 detailed English prompts for '{idea}' in {style} style. No HTML/Markdown/Labels. Double newline separator."
                    with st.spinner("Generating..."):
                        res = mod.generate_content(p)
                        cln = res.text.replace("<br>", "\n").replace("```", "").strip()
                        st.session_state['gen_result'] = cln
                except Exception as e: st.error(str(e))
    with c2:
        if 'gen_result' in st.session_state:
            st.code(st.session_state['gen_result'], language="text")
        else: st.info("Result here.")

# ================= PAGE: HISTORY LOG =================
elif selected_menu == MENU_HISTORY:
    st.subheader("Process History Log")
    st.write("Database records of all successfully processed files.")
    
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button("🗑️ Clear History", type="primary"):
            clear_history()
            st.rerun()

    df_hist = get_history_df()
    if not df_hist.empty:
        st.dataframe(df_hist, use_container_width=True)
        csv = df_hist.to_csv(index=False).encode('utf-8')
        st.download_button("Download Full History (CSV)", csv, "full_history_dump.csv", "text/csv", key='download-csv')
    else:
        st.info("No history records found yet.")