import os
import time
import shutil
import exiftool
import uuid
import sys
from config import BASE_WORK_DIR
from image_ops import StockPhotoOptimizer, get_analysis_image_path, create_xmp_sidecar, detect_blur
from ai_engine import run_gemini_engine, run_openai_compatible_engine
from utils import clean_filename

# --- PORTABLE EXIFTOOL CHECK ---
def get_exiftool_path():
    """Mencari ExifTool di folder 'tools' lokal agar portable."""
    local_tool = os.path.join(os.getcwd(), "tools", "exiftool.exe" if os.name == 'nt' else "exiftool")
    if os.path.exists(local_tool): return local_tool
    return None # Fallback ke System PATH

def determine_file_type(filename):
    ext = os.path.splitext(filename)[1].lower().strip()
    if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.webp']: return "Photo"
    if ext in ['.mp4', '.mov', '.avi', '.mkv']: return "Video"
    if ext in ['.eps', '.ai', '.svg']: return "Vector"
    return "Other"

def process_single_file(filename, provider, model, api_key, base_url, max_retries, options, full_prompt, source_dir, blur_threshold=10.0):
    thread_id = str(uuid.uuid4())[:8]
    source_path = os.path.join(source_dir, filename)
    ftype = determine_file_type(filename)
    
    if not os.path.exists(source_path): return {"status": "error", "msg": "File not found"}

    et_path = get_exiftool_path()

    # --- 1. SKIP EXISTING CHECK ---
    if options.get("skip_existing", False):
        try:
            with exiftool.ExifToolHelper(executable=et_path) as et:
                meta = et.get_tags(source_path, tags=["XMP:Description", "IPTC:Caption-Abstract"])
                for d in meta:
                    if "XMP:Description" in d or "IPTC:Caption-Abstract" in d:
                        return {"status": "skipped", "file": filename, "msg": "Metadata exists"}
        except: pass

    # --- 2. SETUP TEMP FILES ---
    temp_name = f"temp_{thread_id}_{filename}"
    work_path = os.path.join(BASE_WORK_DIR, temp_name)
    shutil.copy2(source_path, work_path)
    
    optimizer = StockPhotoOptimizer()
    preview_path = get_analysis_image_path(work_path) 
    if not preview_path: preview_path = work_path
    
    # --- 3. VISION ANALYSIS & BLUR CHECK ---
    tech_specs = {"context_str": "", "tags": [], "blur_score": 100, "bg_type": "Complex"}
    
    if ftype == "Photo":
        if options.get("blur_check", True):
            # Cek Blur (Logic baru dari image_ops)
            blur_score = detect_blur(work_path, threshold=blur_threshold)
            
            if blur_score < blur_threshold:
                try: os.remove(work_path)
                except: pass
                if preview_path != work_path: 
                    try: os.remove(preview_path)
                    except: pass
                return {"status": "skipped", "file": filename, "msg": f"Blurry (Score: {blur_score:.1f})"}
        
        # Analisis Background, Orientasi, dll
        tech_specs = optimizer.analyze_technical_specs(work_path)

    # Inject Context ke Prompt
    final_prompt = full_prompt + f"\n[TECHNICAL DATA]: {tech_specs['context_str']}"
    if ftype == "Vector": final_prompt += " This is a Vector Illustration."
    if ftype == "Video": final_prompt += " This is a Stock Footage."

    # --- 4. AI INFERENCE ---
    response = None
    last_err = ""
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0: time.sleep(2 * attempt)
            if provider == "Google Gemini (Native)":
                response = run_gemini_engine(model, api_key, preview_path, final_prompt)
            else:
                response = run_openai_compatible_engine(model, api_key, base_url, preview_path, final_prompt)
            if response: break
        except Exception as e: last_err = str(e)
    
    if not response:
        try: os.remove(work_path)
        except: pass
        if preview_path != work_path:
             try: os.remove(preview_path)
             except: pass
        return {"status": "error", "file": filename, "msg": f"AI Fail: {last_err}"}

    # --- 5. POST PROCESS ---
    clean_kw = optimizer.clean_and_optimize_tags(response.get("keywords", ""), tech_specs["tags"])
    title = response.get("title", "").strip()
    desc = f"{title}. {response.get('description', '')}"[:2000]
    
    # [LOGIKA PINTAR SORTIR FOLDER]
    # Jika background 'Solid' atau 'Isolated', kita paksa foldernya sesuai background.
    # Jika background 'Complex', biarkan foldernya sesuai kategori AI (misal: Business, Food).
    detected_bg = tech_specs.get("bg_type", "Complex")
    if detected_bg in ["Isolated White", "Isolated Black", "Solid Color"]:
        final_category = detected_bg # Masuk folder: Output/Photo/Isolated White
    else:
        final_category = response.get("category", "Uncategorized") # Masuk folder: Output/Photo/Business
    
    tags_write = {"XMP:Title": title, "XMP:Description": desc, "XMP:Subject": clean_kw}
    if ftype == "Photo":
        tags_write.update({"IPTC:Headline": title, "IPTC:Caption-Abstract": desc, "IPTC:Keywords": clean_kw})
        
    try:
        with exiftool.ExifToolHelper(executable=et_path) as et:
            et.set_tags(work_path, tags=tags_write, params=["-overwrite_original", "-codedcharacterset=utf8"])
    except Exception as e: print(f"Exif Error: {e}")

    xmp_path = create_xmp_sidecar(work_path, title, desc, clean_kw)
    
    # Rename Logic
    final_name = filename
    if options.get("rename", True):
        ext = os.path.splitext(filename)[1].lower().strip()
        safe_title = clean_filename(title)[:50]
        final_name = f"{safe_title}_{str(uuid.uuid4())[:4]}{ext}"

    if preview_path != work_path and os.path.exists(preview_path):
        try: os.remove(preview_path)
        except: pass

    return {
        "status": "success", "file": filename, "new_name": final_name,
        "file_type": ftype, 
        "category": final_category, # <--- INI KUNCINYA
        "temp_result_path": work_path, "temp_xmp_path": xmp_path,
        "meta_title": title, "meta_desc": desc, "meta_kw": ", ".join(clean_kw),
        "tokens_in": 0, "tokens_out": 0
    }