import streamlit as st
import os
import glob
import time
import shutil
import signal
import pandas as pd
import datetime
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
from streamlit_option_menu import option_menu 
from dotenv import load_dotenv 

# [FIX] Paksa baca ulang .env setiap kali reload agar update real-time
load_dotenv(override=True)

# Import Modul Buatan Sendiri
# NOTE: Jika config.py baru diubah, Anda WAJIB restart terminal (Ctrl+C lalu run lagi)
from config import (
    MODEL_PRICES, PROMPT_PRESETS, PROVIDERS, 
    DEFAULT_INTERNAL_OUTPUT, BASE_WORK_DIR
)
from database import (
    init_db, 
    add_history_entry, get_history_df, clear_history,
    add_prompt_history, get_prompt_history_df, clear_prompt_history
)
from utils import calculate_cost, select_folder_from_wsl, construct_prompt_template
from processor import process_single_file

# Init Database & Folder
init_db()
if not os.path.exists(DEFAULT_INTERNAL_OUTPUT):
    try: os.makedirs(DEFAULT_INTERNAL_OUTPUT)
    except: pass

# ================= KONFIGURASI HALAMAN =================
st.set_page_config(
    page_title="Gemini Studio", 
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= STATE MANAGEMENT =================
DEFAULT_PRESET_KEY = "Commercial (Standard) - BEST SELLER"
if 'active_preset_name' not in st.session_state:
    st.session_state['active_preset_name'] = DEFAULT_PRESET_KEY
    st.session_state['active_title_rule'] = PROMPT_PRESETS[DEFAULT_PRESET_KEY]['title']
    st.session_state['active_desc_rule'] = PROMPT_PRESETS[DEFAULT_PRESET_KEY]['desc']

if 'menu_index' not in st.session_state: st.session_state['menu_index'] = 0 
if 'selected_folder_path' not in st.session_state: st.session_state['selected_folder_path'] = ""
if 'selected_output_path' not in st.session_state: st.session_state['selected_output_path'] = ""

def go_to_metadata(): st.session_state['menu_index'] = 1
def go_to_prompt(): st.session_state['menu_index'] = 2

def update_preset():
    selected = st.session_state.preset_selector
    st.session_state['active_preset_name'] = selected
    st.session_state['active_title_rule'] = PROMPT_PRESETS[selected]['title']
    st.session_state['active_desc_rule'] = PROMPT_PRESETS[selected]['desc']

def handle_input_picker():
    path = select_folder_from_wsl("Pilih Folder SUMBER")
    if path: st.session_state['selected_folder_path'] = path

def handle_output_picker():
    path = select_folder_from_wsl("Pilih Folder TUJUAN")
    if path: st.session_state['selected_output_path'] = path

# ================= SIDEBAR (CLEAN DARK STYLE) =================
with st.sidebar:
    st.markdown("<h3 style='text-align: center; color: white;'>✨ Gemini Studio</h3>", unsafe_allow_html=True)
    st.markdown("---")

    active_api_key = None 

    selected_menu = option_menu(
        menu_title=None, 
        options=["Home", "Metadata Auto", "Prompt Architect", "History Log"], 
        icons=['house', 'camera', 'magic', 'clock'], 
        default_index=st.session_state['menu_index'],
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#e0e0e0", "font-size": "16px"},
            "nav-link": {
                "font-size": "15px", "text-align": "left", "margin": "5px", 
                "--hover-color": "#262730", "color": "#e0e0e0"
            },
            "nav-link-selected": {
                "background-color": "#262730", "color": "#FF4B4B", 
                "font-weight": "600", "border-left": "4px solid #FF4B4B"
            },
        },
        key='sidebar_menu'
    )
    
    st.markdown("---")
    
    # GLOBAL CONFIGURATION
    if selected_menu in ["Metadata Auto", "Prompt Architect"]:
        with st.expander("🤖 AI Model Config", expanded=True):
            st.caption("Provider & Model")
            provider_choice = st.selectbox("Provider", list(PROVIDERS.keys()), index=0, label_visibility="collapsed")
            
            current_provider_config = PROVIDERS[provider_choice]
            
            # [LOGIC FIX] Ambil Variable Name dari config.py
            env_var_name = current_provider_config.get("env_var")
            
            # Coba ambil value dari .env
            detected_key = os.getenv(env_var_name) if env_var_name else None
            
            model_label = st.selectbox("Model", list(current_provider_config["models"].keys()))
            
            if st.checkbox("Use Custom ID"):
                final_model_name = st.text_input("Enter Model ID", value=current_provider_config["models"][model_label])
            else:
                final_model_name = current_provider_config["models"][model_label]
            
            # INPUT API KEY (Logic Key Unik + Auto Fill)
            st.caption(f"Security Key")
            active_api_key = st.text_input(
                "API Key", 
                value=detected_key if detected_key else "", 
                type="password", 
                placeholder=f"Paste Key Here...", 
                label_visibility="collapsed",
                key=f"apikey_{provider_choice}"
            )
            
            # [DEBUG INFO] Memberitahu user status pembacaan .env
            if env_var_name:
                if detected_key:
                    st.caption(f"✅ Loaded from `.env`: `{env_var_name}`")
                else:
                    st.warning(f"⚠️ Missing `{env_var_name}` in .env")

        if selected_menu == "Metadata Auto":
            with st.expander("⚙️ Processing Logic", expanded=False):
                num_workers = st.slider("Threads", 1, 10, 3)
                retry_count = st.slider("Retries", 0, 5, 3)
                blur_limit = st.slider("Blur Threshold", 0.0, 200.0, 100.0)
                st.markdown("---")
                opt_rename = st.checkbox("Auto Rename File", True) 
                opt_folder = st.checkbox("Auto Folder Sort", True)

    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
    c_s1, c_s2 = st.columns(2)
    with c_s1: 
        if st.button("Reload", use_container_width=True): st.rerun()
    with c_s2: 
        if st.button("Stop", type="primary", use_container_width=True): 
            st.warning("Stopping..."); time.sleep(1); os.kill(os.getpid(), signal.SIGTERM)

# ================= PAGE: HOME =================
if selected_menu == "Home":
    st.title("Dashboard")
    st.caption("AI Workflow Automation System")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("**📸 Photos Processed**")
            st.subheader(f"{len(get_history_df())}")
    with c2:
        with st.container(border=True):
            st.markdown("**📝 Prompts Created**")
            st.subheader(f"{len(get_prompt_history_df())}")
    with c3:
        with st.container(border=True):
            st.markdown("**🔌 System Status**")
            if active_api_key: st.markdown(":green[**Online & Ready**]")
            else: st.markdown(":red[**Select Provider to Config**]")

    st.markdown("### Quick Actions")
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        with st.container(border=True):
            st.subheader("Metadata Automation")
            st.write("Generate Title, Description, & Keywords for stock photos.")
            if st.button("🚀 Open Metadata Tool", type="primary", use_container_width=True):
                go_to_metadata(); st.rerun()
                
    with col_nav2:
        with st.container(border=True):
            st.subheader("Prompt Architect")
            st.write("Create detailed prompts for AI Image Generators.")
            if st.button("🎨 Open Prompt Builder", use_container_width=True):
                go_to_prompt(); st.rerun()

# ================= PAGE: METADATA AUTO =================
elif selected_menu == "Metadata Auto":
    st.title("📸 Metadata Automation")

    # SECTION 1: CONFIG
    with st.container(border=True):
        col_L, col_R = st.columns([1, 1])
        
        with col_L:
            st.markdown("##### 1. Folder Selection")
            st.caption("Source Folder")
            c_i1, c_i2 = st.columns([1, 4])
            with c_i1: st.button("Browse", key="btn_in", on_click=handle_input_picker, use_container_width=True)
            with c_i2: st.code(st.session_state['selected_folder_path'] if st.session_state['selected_folder_path'] else "Not selected", language=None)
            
            st.caption("Destination Folder")
            c_o1, c_o2 = st.columns([1, 4])
            with c_o1: st.button("Browse", key="btn_out", on_click=handle_output_picker, use_container_width=True)
            with c_o2: st.code(st.session_state['selected_output_path'] if st.session_state['selected_output_path'] else "Default: Internal Output", language=None)

        with col_R:
            st.markdown("##### 2. Prompt Style")
            st.caption("Choose how the AI describes your images")
            st.selectbox("", options=list(PROMPT_PRESETS.keys()), index=list(PROMPT_PRESETS.keys()).index(st.session_state['active_preset_name']), key="preset_selector", on_change=update_preset, label_visibility="collapsed")
            
            st.markdown("---")
            st.caption("**Active Rules:**")
            st.info(st.session_state['active_title_rule'], icon="ℹ️")

    # SECTION 2: VALIDATION
    ACTIVE_INPUT_DIR = st.session_state['selected_folder_path']
    ACTIVE_OUTPUT_DIR = st.session_state['selected_output_path'] or DEFAULT_INTERNAL_OUTPUT
    
    local_files = []
    if ACTIVE_INPUT_DIR and os.path.exists(ACTIVE_INPUT_DIR):
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.mp4', '*.mov', '*.avi', '*.eps', '*.ai']:
            local_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext)))
            local_files.extend(glob.glob(os.path.join(ACTIVE_INPUT_DIR, ext.upper())))
        local_files = sorted(list(set(local_files)))
    
    if len(local_files) > 0:
        st.write(f"Found **{len(local_files)}** files ready to process.")
        
        with st.expander("💰 Cost Estimator", expanded=False):
            input_est, output_est = 558, 200
            curr_price = MODEL_PRICES["default"]
            for k in MODEL_PRICES:
                if k in final_model_name.lower(): curr_price = MODEL_PRICES[k]; break
            est_cost_unit = ((input_est / 1e6) * curr_price["in"]) + ((output_est / 1e6) * curr_price["out"])
            
            c_lim1, c_lim2 = st.columns(2)
            with c_lim1: files_limit = st.slider("Process Limit", 1, len(local_files), len(local_files))
            with c_lim2: st.metric("Estimated Cost", f"${est_cost_unit * files_limit:.4f}")

        files_to_process = local_files[:files_limit]
        ready = len(files_to_process) > 0 and active_api_key

        if st.button(f"🚀 Start Processing", type="primary", disabled=not ready, use_container_width=True):
            
            DONE_DIR = os.path.join(ACTIVE_INPUT_DIR, "done")
            if not os.path.exists(DONE_DIR): os.makedirs(DONE_DIR)
            
            start_time_total = time.time()
            prompt_str = construct_prompt_template(st.session_state['active_title_rule'], st.session_state['active_desc_rule'])
            opts = {"rename": opt_rename}
            base_url = current_provider_config.get("base_url")

            prog_bar = st.progress(0)
            status_area = st.empty()
            
            with st.container(border=True):
                m1, m2, m3, m4 = st.columns(4)
                with m1: stat_ok = st.empty()
                with m2: stat_skip = st.empty()
                with m3: stat_fail = st.empty()
                with m4: stat_cost = st.empty()

            log_container = st.container(border=True, height=300)
            
            cnt_ok, cnt_skip, cnt_fail, tok_in, tok_out = 0, 0, 0, 0, 0
            csv_data, gallery_images = [], []

            def read_proc(fpath):
                return process_single_file(os.path.basename(fpath), provider_choice, final_model_name, active_api_key, base_url, retry_count, opts, prompt_str, ACTIVE_INPUT_DIR, blur_threshold=blur_limit)

            with ThreadPoolExecutor(max_workers=num_workers) as exe:
                futures = {exe.submit(read_proc, fp): fp for fp in files_to_process}
                
                for i, fut in enumerate(as_completed(futures)):
                    res = fut.result()
                    
                    elapsed = time.time() - start_time_total
                    processed = i + 1
                    avg_time = elapsed / processed
                    eta = avg_time * (len(files_to_process) - processed)
                    status_area.caption(f"⏱️ Time: {elapsed:.1f}s | Avg: {avg_time:.1f}s/file | ETA: {eta:.1f}s")
                    
                    with log_container:
                        if res["status"] == "success":
                            cnt_ok += 1
                            tdir = os.path.join(ACTIVE_OUTPUT_DIR, res['category']) if opt_folder else ACTIVE_OUTPUT_DIR
                            if not os.path.exists(tdir): os.makedirs(tdir)
                            try:
                                shutil.move(res['temp_result_path'], os.path.join(tdir, res['new_name']))
                                if res['temp_xmp_path']: shutil.move(res['temp_xmp_path'], os.path.join(tdir, os.path.splitext(res['new_name'])[0]+".xmp"))
                                shutil.move(os.path.join(ACTIVE_INPUT_DIR, res['file']), os.path.join(DONE_DIR, res['file']))
                                st.success(f"✅ {res['new_name']}")
                                
                                tok_in += res.get("tokens_in", 0); tok_out += res.get("tokens_out", 0)
                                add_history_entry(res['file'], res['new_name'], res['meta_title'], res['meta_desc'], res['meta_kw'], res['category'], tdir)
                                csv_data.append({"Original": res['file'], "New": res['new_name'], "Title": res['meta_title'], "Category": res['category']})
                                if res.get('preview_bytes'): gallery_images.append((res['new_name'], res['preview_bytes']))
                            except Exception as e: st.error(f"Move Error: {e}"); cnt_fail += 1
                        elif res["status"] == "skipped": cnt_skip += 1; st.warning(f"⚠️ {res['file']}: {res['msg']}")
                        else: cnt_fail += 1; st.error(f"❌ {res['file']}: {res['msg']}")

                    prog_bar.progress(processed / len(files_to_process))
                    stat_ok.metric("Success", cnt_ok)
                    stat_skip.metric("Skipped", cnt_skip)
                    stat_fail.metric("Failed", cnt_fail)
                    stat_cost.metric("Real Cost", f"${calculate_cost(final_model_name, tok_in, tok_out):.4f}")

            status_area.success(f"🎉 Batch Complete in {time.time() - start_time_total:.2f}s")
            
            if gallery_images:
                st.markdown("### ✨ Processed Gallery")
                cols = st.columns(4)
                for idx, (name, b) in enumerate(gallery_images):
                    with cols[idx % 4]: st.image(b, caption=name, use_container_width=True)

            if csv_data:
                df = pd.DataFrame(csv_data)
                ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                save_dir = os.path.join(ACTIVE_OUTPUT_DIR, "reports"); os.makedirs(save_dir, exist_ok=True)
                csv_path = os.path.join(save_dir, f"report_{ts}.csv"); df.to_csv(csv_path, index=False)
                st.toast(f"Report saved", icon="📄")
    elif ACTIVE_INPUT_DIR:
        st.info("📁 Please verify the input folder contains images.")
    else:
        st.warning("⚠️ Select an Input Folder to start.")

# ================= PAGE: PROMPT ARCHITECT =================
elif selected_menu == "Prompt Architect":
    st.title("🎨 Prompt Architect")
    
    col_p1, col_p2 = st.columns([1, 1])
    
    # --- LEFT COLUMN: INPUT ---
    with col_p1:
        with st.container(border=True):
            st.markdown("##### 1. Define Idea")
            idea = st.text_area("Input Concept", height=150, placeholder="E.g. A futuristic city in Indonesia with flying batik cars...", label_visibility="collapsed")
            
            c_p1, c_p2 = st.columns(2)
            with c_p1: style = st.selectbox("Visual Style", ["Photorealistic", "Cinematic", "3D Render", "Vector Art", "Macro", "Anime", "Cyberpunk", "Minimalist"])
            with c_p2: num_prompts = st.slider("Variations", 1, 10, 3)
            
            st.markdown("---")
            if st.button("Generate Prompts 🪄", type="primary", use_container_width=True, disabled=not active_api_key):
                if not idea: st.warning("Enter an idea first.")
                else:
                    try:
                        genai.configure(api_key=active_api_key)
                        mod = genai.GenerativeModel(final_model_name)
                        p = f"Role: Expert AI Prompt Engineer. Task: Write {num_prompts} distinct, highly detailed English prompts for '{idea}' in {style} style. Constraints: Return ONLY the raw prompts separated by double newlines. Do not include numbering, labels, introduction, or markdown styling."
                        with st.spinner(f"Generating..."):
                            res = mod.generate_content(p)
                            clean_result = res.text.replace("*", "").replace("#", "").strip()
                            st.session_state['gen_result'] = clean_result
                            add_prompt_history(idea, style, final_model_name, clean_result)
                            st.toast("Saved to History", icon="💾")
                    except Exception as e: st.error(str(e))

    # --- RIGHT COLUMN: RESULT ---
    with col_p2:
        with st.container(border=True):
            st.markdown("##### 2. Result")
            if 'gen_result' in st.session_state:
                st.caption("💡 Hover top-right to Copy")
                st.code(st.session_state['gen_result'], language="text")
            else:
                st.info("Results will appear here...")

# ================= PAGE: HISTORY =================
elif selected_menu == "History Log":
    st.title("📜 Process History")
    
    tab_meta, tab_prompt = st.tabs(["📸 Metadata Logs", "🎨 Prompt Logs"])
    
    with tab_meta:
        c_h1, c_h2 = st.columns([5,1])
        with c_h2: 
            if st.button("Trash Metadata", type="primary", use_container_width=True): clear_history(); st.rerun()
        
        df = get_history_df()
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", df.to_csv(index=False).encode('utf-8'), "meta_log.csv", "text/csv")
        else: st.info("Empty records.")
            
    with tab_prompt:
        c_hp1, c_hp2 = st.columns([5,1])
        with c_hp2: 
            if st.button("Trash Prompts", type="primary", use_container_width=True): clear_prompt_history(); st.rerun()
        
        df_p = get_prompt_history_df()
        if not df_p.empty:
            st.dataframe(df_p, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", df_p.to_csv(index=False).encode('utf-8'), "prompt_log.csv", "text/csv")
        else: st.info("Empty records.")