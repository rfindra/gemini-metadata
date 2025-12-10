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

# Import Modul Buatan Sendiri (Pastikan file-file ini ada di folder yang sama)
from config import (
    MODEL_PRICES, PROMPT_PRESETS, PROVIDERS, 
    DEFAULT_INTERNAL_OUTPUT, BASE_WORK_DIR
)
from database import init_db, add_history_entry, get_history_df, clear_history
from utils import calculate_cost, select_folder_from_wsl, construct_prompt_template
from processor import process_single_file

# Init Database
init_db()

# Cek Folder Output
if not os.path.exists(DEFAULT_INTERNAL_OUTPUT):
    try: os.makedirs(DEFAULT_INTERNAL_OUTPUT)
    except: pass

# ================= KONFIGURASI HALAMAN =================
st.set_page_config(
    page_title="Gemini Metadata Studio", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
                
                # --- [UPDATE] UI SETTINGS RETRY & BLUR ---
                retry_count = st.slider("Max Retries (Jika Error)", 0, 5, 3, help="Jumlah percobaan ulang otomatis jika koneksi gagal.")
                blur_limit = st.slider("Blur Threshold (Anti-Boncos)", 0.0, 300.0, 0.0, step=10.0, help="0 = Mati. 100-150 = Standar. Jika skor blur di bawah angka ini, file di-skip (Hemat API).")
                # -----------------------------------------
                
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
        
        # COST PREVIEW & LIMITER SECTION
        if len(local_files) > 0:
            st.divider()
            st.markdown("### 📊 Estimasi & Limit (Anti Boncos)")
            
            input_est_unit = 558
            output_est_unit = 200
            
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
                
                # --- Setup Folder DONE ---
                DONE_DIR = os.path.join(ACTIVE_INPUT_DIR, "done")
                if not os.path.exists(DONE_DIR):
                    os.makedirs(DONE_DIR)

                # --- Timer Start ---
                start_time_total = time.time()

                log_cont = st.container(height=400, border=True)
                log_cont.empty()
                st.toast("Processing...")
                
                c1, c2, c3 = st.columns(3)
                with c1: stat_success = st.metric("Success", "0")
                with c2: stat_fail = st.metric("Fail", "0")
                with c3: st.metric("Target", str(len(files_to_process)))

                time_metric_display = st.empty()
                
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
                        # [UPDATE] Pass variable retry_count dan blur_limit ke fungsi processor
                        return process_single_file(
                            fname, provider_choice, final_model_name, api_key, base_url, 
                            retry_count, opts, prompt_str, ACTIVE_INPUT_DIR, 
                            blur_threshold=blur_limit
                        )
                    except Exception as e: return {"status": "error", "file": fname, "msg": str(e)}

                with ThreadPoolExecutor(max_workers=num_workers) as exe:
                    futures = {exe.submit(read_proc, fp): fp for fp in files_to_process}
                    for i, fut in enumerate(as_completed(futures)):
                        
                        # Update Timer Logic
                        current_time = time.time()
                        elapsed = current_time - start_time_total
                        processed_cnt = i + 1
                        avg_time = elapsed / processed_cnt
                        remaining_files = len(files_to_process) - processed_cnt
                        eta_seconds = avg_time * remaining_files
                        
                        time_metric_display.markdown(
                            f"⏱️ **Time:** {elapsed:.1f}s | 🚀 **Avg:** {avg_time:.1f}s/file | ⏳ **ETA:** {eta_seconds:.1f}s"
                        )

                        res = fut.result()
                        with log_cont:
                            if res["status"] == "success":
                                count_ok += 1
                                cat = res['category']
                                fname = res['new_name']
                                temp_path = res['temp_result_path']
                                temp_xmp = res['temp_xmp_path']
                                
                                t_in = res.get("tokens_in", 0)
                                t_out = res.get("tokens_out", 0)
                                total_tokens_in += t_in
                                total_tokens_out += t_out
                                
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

                                    # Move Original File to DONE
                                    try:
                                        source_original_path = os.path.join(ACTIVE_INPUT_DIR, res['file'])
                                        destination_done_path = os.path.join(DONE_DIR, res['file'])
                                        shutil.move(source_original_path, destination_done_path)
                                    except Exception as e_move:
                                        st.error(f"Gagal memindahkan ke folder done: {e_move}")

                                except Exception as e:
                                    st.error(f"Move Error: {e}")
                            
                            # [UPDATE] Penanganan File yang di-Skip (Blur/Rejected)
                            elif res["status"] == "skipped":
                                st.warning(f"⚠️ `{res['file']}`: {res['msg']}")
                            
                            else:
                                count_err += 1
                                st.markdown(f"❌ `{res['file']}`: {res['msg']}")
                                
                        prog_bar.progress((i+1)/len(files_to_process))
                        stat_success.metric("Success", count_ok)
                        stat_fail.metric("Fail", count_err)
                
                st.success(f"Batch Complete. Total Waktu: {time.time() - start_time_total:.2f} detik.")
                
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