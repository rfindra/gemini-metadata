# processor.py
import os
import time
import shutil
import exiftool
from config import BASE_WORK_DIR
from image_ops import StockPhotoOptimizer, get_analysis_image_path, create_xmp_sidecar
from ai_engine import run_gemini_engine, run_openai_compatible_engine
from utils import clean_filename

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