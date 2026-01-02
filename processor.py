# processor.py
import os
import time
import shutil
import uuid
import io
import gc
import cv2
import numpy as np
from PIL import Image

# Import modules
from config import BASE_WORK_DIR
from image_ops import create_xmp_sidecar
from ai_engine import run_gemini_engine, run_openai_compatible_engine
from utils import clean_filename

# --- HELPER: In-Memory Blur ---
def detect_blur_in_memory(cv2_image, threshold=5.0):
    try:
        if cv2_image is None: return 0.0
        if len(cv2_image.shape) == 3: gray = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2GRAY)
        else: gray = cv2_image
        return cv2.Laplacian(gray, cv2.CV_64F).var()
    except: return 0.0

def determine_file_type(filename):
    ext = os.path.splitext(filename)[1].lower().strip()
    if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.webp']: return "Photo"
    if ext in ['.mp4', '.mov', '.avi', '.mkv']: return "Video"
    if ext in ['.eps', '.ai', '.svg']: return "Vector"
    return "Other"

# --- MAIN PROCESSOR (Metadata Generator Only) ---
# [UPDATE] Menambahkan parameter 'user_correction'
def process_single_file(filename, provider, model, api_key, base_url, max_retries, options, full_prompt, source_dir, custom_temp_dir=None, blur_threshold=10.0, user_correction=None):
    thread_id = str(uuid.uuid4())[:8]
    source_path = os.path.join(source_dir, filename)
    ftype = determine_file_type(filename)
    
    # Tentukan folder kerja (RAMDisk atau Default)
    working_dir = custom_temp_dir if custom_temp_dir and os.path.exists(custom_temp_dir) else BASE_WORK_DIR
    
    # Preview Path
    preview_filename = f"ai_preview_{thread_id}.jpg"
    preview_path = os.path.join(working_dir, preview_filename)
    
    if not os.path.exists(source_path): 
        return {"status": "error", "msg": "File not found"}

    try:
        # --- 1. SMART LOADING (RAM Optimized) ---
        ai_input_data = None 
        tech_specs = {"context_str": "", "tags": [], "bg_type": "Complex"}
        
        # [ALUR FOTO - RAM MODE]
        if ftype == "Photo":
            with open(source_path, "rb") as f: file_bytes = f.read()
            img_pil = Image.open(io.BytesIO(file_bytes)).convert("RGB")
            
            # Blur Check (Di RAM)
            if options.get("blur_check", True):
                img_np = np.array(img_pil) 
                img_cv2 = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                blur_score = detect_blur_in_memory(img_cv2)
                
                if blur_score < blur_threshold:
                    del file_bytes, img_pil, img_np, img_cv2
                    gc.collect()
                    return {"status": "skipped", "file": filename, "msg": f"Blurry (Score: {blur_score:.1f})"}
                del img_np, img_cv2 
            
            # Resize (Di RAM)
            img_pil.thumbnail((1024, 1024))
            
            # Save ke Buffer Memory
            img_byte_arr = io.BytesIO()
            img_pil.save(img_byte_arr, format="JPEG", quality=80)
            ai_input_data = img_byte_arr.getvalue()
            
            # Tech Specs
            w, h = img_pil.size
            if w > h: tech_specs["tags"].append("horizontal")
            elif h > w: tech_specs["tags"].append("vertical")
            
            del file_bytes, img_pil, img_byte_arr
            gc.collect()

        # [ALUR VIDEO]
        elif ftype == "Video":
            cap = cv2.VideoCapture(source_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret, frame = cap.read()
            cap.release()
            
            if not ret: return {"status": "error", "file": filename, "msg": "Video corrupt"}
            
            h, w, _ = frame.shape
            if w > 1024:
                scale = 1024 / w
                frame = cv2.resize(frame, (1024, int(h * scale)))
            
            success, encoded_img = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if success:
                ai_input_data = encoded_img.tobytes()
                tech_specs["context_str"] = "This is a Stock Footage/Video."
            
            del frame, encoded_img
            gc.collect()

        # [ALUR VECTOR]
        elif ftype == "Vector":
            import subprocess
            # WSL menggunakan 'gs' standard Linux
            args = ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=jpeg", "-dEPSCrop", "-r150", 
                   f"-sOutputFile={preview_path}", source_path]
            subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(preview_path):
                with open(preview_path, "rb") as f:
                    ai_input_data = f.read()
                try: os.remove(preview_path)
                except: pass
                tech_specs["context_str"] = "This is a Vector Illustration."
            else:
                return {"status": "error", "file": filename, "msg": "Vector convert failed"}

        if not ai_input_data:
             return {"status": "error", "file": filename, "msg": "Failed to prepare image data"}

        # --- 2. AI INFERENCE (Dengan User Correction Support) ---
        
        tech_data_str = f"[TECHNICAL DATA]: {tech_specs['context_str']} {', '.join(tech_specs['tags'])}"

        # Logic Injection Prompt
        if user_correction:
            final_prompt = f"""
            {full_prompt}
            
            [🚨 CRITICAL USER OVERRIDE]: 
            The user has provided specific instructions for this image. You MUST prioritize this over your visual analysis.
            USER INSTRUCTION: "{user_correction}"
            
            Refine the Title, Description, and Keywords to strictly align with the user's instruction above.
            
            {tech_data_str}
            """
        else:
            # Standar Prompt
            final_prompt = full_prompt + "\n" + tech_data_str
        
        response = None
        last_err = ""
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0: time.sleep(2 * attempt)
                if provider == "Google Gemini (Native)":
                    response = run_gemini_engine(model, api_key, ai_input_data, final_prompt)
                else:
                    response = run_openai_compatible_engine(model, api_key, base_url, ai_input_data, final_prompt)
                if response: break
            except Exception as e: last_err = str(e)
        
        if not response:
            return {"status": "error", "file": filename, "msg": f"AI Fail: {last_err}"}

        # --- 3. DATA PREPARATION ---
        raw_kw = response.get("keywords", [])
        if isinstance(raw_kw, str): raw_kw = raw_kw.split(',')
        clean_kw = [k.strip().lower() for k in raw_kw if len(k) > 2][:49]
        
        title = response.get("title", "").strip()
        clean_title = title.replace('"', '').replace("'", "")
        category = response.get("category", "Uncategorized")
        
        raw_ai_desc = response.get('description', '')
        if clean_title.lower() in raw_ai_desc.lower()[:len(clean_title)+5]:
            combined_desc = raw_ai_desc 
        else:
            combined_desc = f"{clean_title}. {raw_ai_desc}"
            
        final_subject_desc = combined_desc[:190].strip()
        if final_subject_desc.endswith(('.', ',')): 
            final_subject_desc = final_subject_desc[:-1] + "."
        elif not final_subject_desc.endswith('.'):
            final_subject_desc += "."

        flat_kw_windows = ";".join(clean_kw)
        flat_kw_comma = ", ".join(clean_kw)
        
        final_name = filename
        if options.get("rename", True):
            ext = os.path.splitext(filename)[1].lower()
            safe_title = clean_filename(clean_title)[:50]
            # UUID tetap dipakai untuk keunikan
            final_name = f"{safe_title}_{str(uuid.uuid4())[:4]}{ext}"

        # --- METADATA MAPPING ---
        tags_to_write = {
            "XMP:Title": clean_title,
            "XMP:Description": final_subject_desc, 
            "XMP:Subject": clean_kw,
            "IPTC:Headline": clean_title,
            "IPTC:Caption-Abstract": final_subject_desc,
            "IPTC:Keywords": clean_kw,
            "EXIF:XPTitle": clean_title,         
            "EXIF:XPKeywords": flat_kw_windows,  
            "EXIF:XPSubject": final_subject_desc,
            "EXIF:XPComment": final_subject_desc,
            "EXIF:ImageDescription": final_subject_desc,
            "XMP:Rating": 5
        }

        gc.collect()

        return {
            "status": "success", 
            "file": filename,
            "original_path": source_path, 
            "new_name": final_name,
            "file_type": ftype, 
            "category": category,
            "tags_data": tags_to_write, 
            "meta_title": clean_title, 
            "meta_desc": final_subject_desc, 
            "meta_kw": flat_kw_comma,
            "preview_bytes": None 
        }

    except Exception as e:
        if 'preview_path' in locals() and os.path.exists(preview_path):
            try: os.remove(preview_path)
            except: pass
        return {"status": "error", "file": filename, "msg": str(e)}