import os
import time
import shutil
import exiftool
from config import BASE_WORK_DIR
from image_ops import StockPhotoOptimizer, get_analysis_image_path, create_xmp_sidecar, detect_blur
from ai_engine import run_gemini_engine, run_openai_compatible_engine
from utils import clean_filename

def determine_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']: return "Photo"
    if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']: return "Video"
    if ext in ['.eps', '.ai', '.svg']: return "Vector"
    return "Other"

def process_single_file(filename, provider_type, model_name, api_key, base_url, max_retries, options, full_prompt_string, source_dir, blur_threshold=0.0):
    thread_id = str(time.time()).replace('.', '')
    
    source_full_path = os.path.join(source_dir, filename)
    file_type = determine_file_type(filename)
    
    if not os.path.exists(source_full_path):
        return {"status": "error", "file": filename, "msg": "File sumber hilang."}

    # --- SKIP PROCESSED ---
    if options.get("skip_existing", False):
        try:
            with exiftool.ExifToolHelper() as et:
                metadata = et.get_tags(source_full_path, tags=["XMP:Description", "IPTC:Caption-Abstract", "XMP:Subject"])
                for d in metadata:
                    if "XMP:Description" in d or "IPTC:Caption-Abstract" in d:
                        return {"status": "skipped", "file": filename, "msg": "Metadata existing."}
        except: pass

    # --- BLUR CHECK ---
    if file_type == "Photo":
        is_blurry, blur_score = detect_blur(source_full_path, threshold=blur_threshold)
        if is_blurry:
            return {"status": "skipped", "file": filename, "msg": f"Blurry ({blur_score:.1f})"}

    temp_file_name = f"temp_{thread_id}_{filename}"
    working_path = os.path.join(BASE_WORK_DIR, temp_file_name)
    
    preview_path = None
    preview_bytes = None
    optimizer = StockPhotoOptimizer()
    
    try:
        shutil.copy2(source_full_path, working_path)
        preview_path = get_analysis_image_path(working_path)
        
        if not preview_path or not os.path.exists(preview_path):
            if file_type == "Video":
                return {"status": "error", "file": filename, "msg": "Gagal extract frame video."}
            preview_path = working_path 
        
        try:
            with open(preview_path, "rb") as fimg:
                preview_bytes = fimg.read()
        except: pass

        tech_specs = optimizer.analyze_technical_specs(preview_path)
        context_injection = tech_specs['context_str']
        if file_type == "Vector": context_injection += " This is a Vector Illustration (EPS/AI)."
        if file_type == "Video": context_injection += " This is a Stock Footage/Video."
        
        prompt = full_prompt_string.replace("{context_injection}", context_injection)
        
        response_data = None
        last_error = ""
        
        for attempt in range(max_retries + 1): 
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
                if "429" in last_error: time.sleep(10 + (attempt * 5))
        
        if not response_data:
            return {"status": "error", "file": filename, "msg": f"AI Fail: {last_error}"}

        # --- DATA PROCESSING & MERGING TITLE/DESC ---
        raw_kw = response_data.get("keywords", "")
        kw = optimizer.clean_and_optimize_tags(raw_kw, tech_specs["tags"])
        kw = kw[:49] 

        title = response_data.get("title", "").strip()[:200]
        raw_desc = response_data.get("description", "").strip()
        category = response_data.get("category", "Uncategorized")
        
        # [MODIFIKASI UTAMA] Gabungkan Title + Mood Description
        # Pastikan tidak ada titik ganda
        clean_title = title.rstrip('.')
        final_desc = f"{clean_title}. {raw_desc}"[:2000] # Gabungkan!

        # --- WRITE METADATA ---
        tags_to_write = {
            "XMP:Title": title,
            "XMP:Description": final_desc, # Gunakan deskripsi gabungan
            "XMP:Subject": kw
        }

        if file_type == "Photo":
            tags_to_write.update({
                "IPTC:Headline": title, 
                "IPTC:Caption-Abstract": final_desc, # Gunakan deskripsi gabungan
                "IPTC:Keywords": kw,
                "EXIF:XPTitle": title, 
                "EXIF:XPKeywords": ";".join(kw), 
                "EXIF:ImageDescription": final_desc # Gunakan deskripsi gabungan
            })
        elif file_type == "Vector":
             tags_to_write.update({ "IPTC:Headline": title, "IPTC:Keywords": kw })
        
        try:
            with exiftool.ExifToolHelper() as et:
                et.set_tags(working_path, tags=tags_to_write, params=["-overwrite_original", "-codedcharacterset=utf8"])
        except Exception as e: print(f"Exiftool Warning: {e}")

        temp_xmp_path = create_xmp_sidecar(os.path.splitext(working_path)[0], title, final_desc, kw)
        
        final_name = filename
        if options["rename"]:
            safe_title = clean_filename(title)
            ext = os.path.splitext(filename)[1].lower()
            final_name = f"{safe_title}{ext}"
        
        return {
            "status": "success", 
            "file": filename, 
            "new_name": final_name,
            "file_type": file_type,
            "category": category, 
            "temp_result_path": working_path, 
            "temp_xmp_path": temp_xmp_path, 
            "meta_title": title, 
            "meta_desc": final_desc, # Return deskripsi gabungan untuk CSV juga
            "meta_kw": ", ".join(kw),
            "preview_bytes": preview_bytes,
            "tokens_in": 300, "tokens_out": 200
        }
        
    except Exception as e:
        if os.path.exists(working_path): 
            try: os.remove(working_path)
            except: pass
        return {"status": "error", "file": filename, "msg": f"Sys Error: {str(e)}"}
        
    finally:
        if preview_path and preview_path != working_path and os.path.exists(preview_path): 
            os.remove(preview_path)