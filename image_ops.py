import cv2
import numpy as np
import os
import subprocess
from PIL import Image, ImageStat

# --- 1. GPU AUTO-DETECT ---
try:
    import cupy as cp
    HAS_GPU = True
    print("[INFO] NVIDIA GPU Detected: Acceleration Enabled")
except ImportError:
    import numpy as cp
    HAS_GPU = False
    print("[WARN] GPU Not Found: Running on CPU mode")

# --- 2. SPEED OPTIMIZED BLUR DETECTION (FFT) ---

def calculate_fft_score(img_array, size=30): 
    h, w = img_array.shape
    if h < size*2 or w < size*2: return 0.0
    
    (cX, cY) = (int(w / 2.0), int(h / 2.0))

    if HAS_GPU:
        gpu_img = cp.asarray(img_array)
        fft = cp.fft.fft2(gpu_img)
        fftShift = cp.fft.fftshift(fft)
        fftShift[cY - size:cY + size, cX - size:cX + size] = 0 
        fftShift = cp.fft.ifftshift(fftShift)
        recon = cp.fft.ifft2(fftShift)
        magnitude = cp.log(cp.abs(recon) + 1) 
        return float(cp.mean(magnitude)) * 20
    else:
        fft = np.fft.fft2(img_array)
        fftShift = np.fft.fftshift(fft)
        fftShift[cY - size:cY + size, cX - size:cX + size] = 0
        fftShift = np.fft.ifftshift(fftShift)
        recon = np.fft.ifft2(fftShift)
        magnitude = np.log(np.abs(recon) + 1)
        return np.mean(magnitude) * 20

def detect_blur(image_path, threshold=0.0):
    if threshold <= 0: return 0.0
    
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None: return 0.0

        h, w = img.shape
        target_w = 512 
        if w > target_w:
            scale = target_w / w
            new_dim = (target_w, int(h * scale))
            img = cv2.resize(img, new_dim, interpolation=cv2.INTER_NEAREST)
            h, w = img.shape

        M, N = 3, 3 
        tiles = []
        step_y = h // M
        step_x = w // N
        
        for y in range(0, M):
            for x in range(0, N):
                y1 = y * step_y
                x1 = x * step_x
                tile = img[y1:y1+step_y, x1:x1+step_x]
                if tile.size > 0: tiles.append(tile)

        if not tiles: return 0.0

        scores = []
        for tile in tiles:
            scores.append(calculate_fft_score(tile))

        scores.sort(reverse=True)
        top_scores = scores[:2]
        final_score = sum(top_scores) / len(top_scores)
        
        return final_score

    except Exception as e: return 0.0

# --- 3. BACKGROUND SORTING LOGIC ---

def analyze_background_type(image_path):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail((100, 100)) 
            img_np = np.array(img)
            
        h, w, _ = img_np.shape
        s = 15 

        corners = [
            img_np[0:s, 0:s],           
            img_np[0:s, w-s:w],         
            img_np[h-s:h, 0:s],         
            img_np[h-s:h, w-s:w],       
            img_np[0:s, int(w/2)-5:int(w/2)+5] 
        ]
        
        samples_cpu = np.concatenate([c.reshape(-1, 3) for c in corners])

        if HAS_GPU:
            samples_gpu = cp.asarray(samples_cpu)
            std_dev = float(cp.std(samples_gpu, axis=0).mean())
            mean_color = cp.asnumpy(cp.mean(samples_gpu, axis=0))
        else:
            std_dev = np.std(samples_cpu, axis=0).mean()
            mean_color = np.mean(samples_cpu, axis=0)
        
        if std_dev < 20.0: 
            if mean_color[0]>240 and mean_color[1]>240 and mean_color[2]>240: 
                return "Isolated White", "Isolated on white background"
            elif mean_color[0]<20 and mean_color[1]<20 and mean_color[2]<20: 
                return "Isolated Black", "Isolated on black background"
            else: 
                return "Solid Color", "Studio shot with solid colored background"
        
        return "Complex", "Natural environment background"
    except: 
        return "Complex", "Natural background"

# --- 4. HELPERS ---

def create_xmp_sidecar(path_without_ext, title, desc, keywords):
    try:
        rdf_keywords = "\n".join([f"<rdf:li>{k}</rdf:li>" for k in keywords])
        xmp = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'><rdf:Description rdf:about='' xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title><rdf:Alt><rdf:li xml:lang='x-default'>{title}</rdf:li></rdf:Alt></dc:title><dc:description><rdf:Alt><rdf:li xml:lang='x-default'>{desc}</rdf:li></rdf:Alt></dc:description><dc:subject><rdf:Bag>{rdf_keywords}</rdf:Bag></dc:subject></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end='w'?>"""
        with open(f"{path_without_ext}.xmp", "w", encoding="utf-8") as f: f.write(xmp)
        return f"{path_without_ext}.xmp"
    except: return None

# [UPDATED] Fungsi ini sekarang me-resize gambar besar sebelum dikirim ke AI
def get_analysis_image_path(original_file_path):
    """
    Menyiapkan 'Mata' untuk AI.
    - Video/Vector: Ambil frame/convert.
    - Foto Besar (>1024px): Resize ke 1024px (Preview).
    - Foto Kecil: Pakai asli.
    """
    try:
        ext = os.path.splitext(original_file_path)[1].lower()
        temp_img_path = original_file_path + "_preview.jpg"
        
        # 1. Handle VIDEO (Ambil Frame Tengah)
        if ext in ['.mp4', '.mov', '.avi', '.mkv']:
            cap = cv2.VideoCapture(original_file_path)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2 if total > 0 else 0)
            ret, frame = cap.read()
            cap.release()
            if ret:
                # Resize frame video jika terlalu besar
                h, w, _ = frame.shape
                if w > 1024:
                    scale = 1024 / w
                    frame = cv2.resize(frame, (1024, int(h * scale)))
                cv2.imwrite(temp_img_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                return temp_img_path
            return None

        # 2. Handle VECTOR (Convert ke JPG pakai Ghostscript)
        elif ext in ['.eps', '.ai']:
            args = ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=jpeg", "-dEPSCrop", "-r150", f"-sOutputFile={temp_img_path}", original_file_path]
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_img_path): return temp_img_path
            return None

        # 3. Handle FOTO BIASA (Resize ke 1024px max)
        else:
            with Image.open(original_file_path) as img:
                # Convert ke RGB (jika CMYK/RGBA) agar bisa di-save sebagai JPEG
                if img.mode not in ('L', 'RGB'):
                    img = img.convert('RGB')
                
                # Cek ukuran, jika lebar/tinggi > 1024px, kecilkan!
                w, h = img.size
                if w > 1024 or h > 1024:
                    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    img.save(temp_img_path, "JPEG", quality=80)
                    return temp_img_path
                else:
                    # Jika sudah kecil, tetap return path asli (biar gak menuhin storage)
                    return original_file_path

    except Exception as e:
        print(f"[WARN] Gagal membuat preview: {e}")
        return original_file_path # Fallback ke file asli jika gagal

# --- 5. MAIN CLASS ---

class StockPhotoOptimizer:
    def __init__(self):
        self.universal_blacklist = {"vector", "illustration", "drawing", "painting", "generated", "ai generated", "render", "3d", "artwork"}
        self.high_value_tech_tags = {"no people", "isolated", "white background", "copy space", "solid background"}

    def analyze_technical_specs(self, image_path):
        specs = {"tags": [], "context_str": "", "blur_score": 0.0, "bg_type": "Complex"}
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                if w > h: specs["tags"].append("horizontal")
                elif h > w: specs["tags"].append("vertical")
                else: specs["tags"].append("square")

            specs["blur_score"] = detect_blur(image_path)
            bg_type, bg_desc = analyze_background_type(image_path)
            specs["bg_type"] = bg_type

            parts = [f"Background Style: {bg_desc}."]
            if bg_type == "Isolated White": 
                specs["tags"].extend(["white background", "isolated"])
            elif bg_type == "Isolated Black": 
                specs["tags"].extend(["black background", "isolated"])
            elif bg_type == "Solid Color":
                specs["tags"].extend(["solid background", "copy space", "studio shot", "minimalist"])
                parts.append("Key Visual: Minimalist composition with solid color background.")
            
            if specs["blur_score"] > 20: parts.append("Sharp focus.")
            elif specs["blur_score"] < 10: parts.append("Soft focus/Blur.")

            specs["context_str"] = " ".join(parts)
            return specs
        except: return specs

    def clean_and_optimize_tags(self, ai_keywords, technical_tags):
        if isinstance(ai_keywords, list): ai_tokens = [str(t).strip().lower() for t in ai_keywords]
        else: ai_tokens = [t.strip().lower() for t in (ai_keywords or "").split(",")]
        tech_tokens = [t.strip().lower() for t in technical_tags]
        final = []
        seen = set()
        pool = ai_tokens[:5] + [t for t in tech_tokens if t in self.high_value_tech_tags] + ai_tokens[5:] + tech_tokens
        for t in pool:
            import re
            c = re.sub(r"[^a-z0-9\s-]", "", t).strip()
            if len(c)>2 and c not in seen and c not in self.universal_blacklist:
                final.append(c); seen.add(c)
        return final[:49]

# --- 6. HYBRID SIMILARITY CHECKER (Structure + Color) ---

def compute_dhash(image_path, hash_size=16):
    """
    [UPGRADED] Mengembalikan Dictionary berisi Struktur dan Data Warna.
    """
    try:
        # 1. Load Image
        img = cv2.imread(image_path)
        if img is None: return None
        
        # 2. Structure Hash (dHash Grayscale 16-bit)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized_gray = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        diff = resized_gray[:, 1:] > resized_gray[:, :-1]
        structure_hash = sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])
        
        # 3. Color Signature (9x9 Low Res Grid - Flattened)
        resized_color = cv2.resize(img, (9, 9), interpolation=cv2.INTER_AREA)
        color_sig = resized_color.flatten() # Array panjang (R, G, B, R, G, B...)
        
        return {
            "structure": structure_hash,
            "color": color_sig
        }
    except:
        return None

def calculate_similarity_percentage(hash1, hash2, hash_size=16):
    """
    Menghitung kemiripan dengan logika VETO.
    Jika Struktur mirip TAPI Warna beda -> BUKAN Duplikat.
    """
    if hash1 is None or hash2 is None: return 0.0
    
    # 1. Cek Struktur (dHash)
    s1, s2 = hash1["structure"], hash2["structure"]
    hamming_dist = bin(int(s1) ^ int(s2)).count('1')
    total_bits = hash_size * hash_size
    struct_sim = (total_bits - hamming_dist) / total_bits * 100
    
    # Jika struktur sudah sangat berbeda (<70%), langsung return (Optimasi Speed)
    if struct_sim < 70:
        return struct_sim
        
    # 2. Cek Warna (Hanya jika struktur mirip)
    c1, c2 = hash1["color"], hash2["color"]
    dist = np.mean(np.abs(c1 - c2))
    
    # Konversi Distance ke Similarity %
    color_sim = max(0, 100 - (dist * 1.5))
    
    # 3. Final Verdict (Hybrid Logic)
    final_sim = min(struct_sim, color_sim)
    
    return final_sim