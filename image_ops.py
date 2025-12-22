import cv2
import numpy as np
import os
import subprocess
from PIL import Image, ImageStat

# --- 1. GPU AUTO-DETECT ---
try:
    import cupy as cp
    HAS_GPU = True
    print("🚀 NVIDIA GPU Detected: Smart Blur Engine Enabled (CuPy)")
except ImportError:
    import numpy as cp
    HAS_GPU = False
    print("⚠️ GPU Not Found: Running on CPU mode")

# --- 2. ADVANCED BLUR DETECTION (GRID STRATEGY) ---

def calculate_fft_score(img_array, size=60):
    """
    Menghitung skor ketajaman satu potongan gambar menggunakan FFT.
    """
    h, w = img_array.shape
    if h < size*2 or w < size*2: return 0.0
    
    (cX, cY) = (int(w / 2.0), int(h / 2.0))

    if HAS_GPU:
        # GPU Calculation
        gpu_img = cp.asarray(img_array)
        fft = cp.fft.fft2(gpu_img)
        fftShift = cp.fft.fftshift(fft)
        fftShift[cY - size:cY + size, cX - size:cX + size] = 0 # Block low freq
        fftShift = cp.fft.ifftshift(fftShift)
        recon = cp.fft.ifft2(fftShift)
        magnitude = 20 * cp.log(cp.abs(recon) + 1)
        return float(cp.mean(magnitude))
    else:
        # CPU Calculation
        fft = np.fft.fft2(img_array)
        fftShift = np.fft.fftshift(fft)
        fftShift[cY - size:cY + size, cX - size:cX + size] = 0
        fftShift = np.fft.ifftshift(fftShift)
        recon = np.fft.ifft2(fftShift)
        magnitude = 20 * np.log(np.abs(recon) + 1)
        return np.mean(magnitude)

def detect_blur(image_path, threshold=0.0):
    """
    [NAMA DISESUAIKAN]
    Logika tetap menggunakan 'Smart Bokeh' (Grid 4x4 FFT).
    Mengambil rata-rata dari 3 area paling tajam (mengabaikan background blur).
    """
    if threshold <= 0: return 0.0 # Bypass jika threshold 0
    
    try:
        # Baca gambar sebagai Grayscale
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None: return 0.0

        # Resize agar konsisten (max lebar 1024px)
        h, w = img.shape
        target_w = 1024
        if w > target_w:
            scale = target_w / w
            new_dim = (target_w, int(h * scale))
            img = cv2.resize(img, new_dim, interpolation=cv2.INTER_AREA)
            h, w = img.shape

        # Tentukan Grid (4x4 = 16 Potongan)
        M, N = 4, 4 
        tiles = []
        
        # Potong gambar jadi tiles
        for y in range(0, h, h // M):
            for x in range(0, w, w // N):
                tile = img[y:y + h // M, x:x + w // N]
                if tile.shape[0] > 0 and tile.shape[1] > 0:
                    tiles.append(tile)

        scores = []
        for tile in tiles:
            # Hitung skor FFT untuk setiap kotak
            score = calculate_fft_score(tile)
            scores.append(score)

        if not scores: return 0.0

        # --- LOGIKA "SMART BOKEH" ---
        # Urutkan dari yang paling tajam
        scores.sort(reverse=True)
        
        # Ambil rata-rata dari 3 kotak paling tajam saja (Top 3)
        top_scores = scores[:3]
        final_score = sum(top_scores) / len(top_scores)
        
        return final_score

    except Exception as e:
        print(f"Blur Error: {e}")
        return 0.0

# --- 3. BACKGROUND ANALYSIS ---

def analyze_background_type(image_path):
    try:
        img_pil = Image.open(image_path).convert("RGB")
        img_np = np.array(img_pil)
        h, w, _ = img_np.shape

        s = 50 if h > 100 else 10
        corners = [
            img_np[0:s,0:s], img_np[0:s,w-s:w], 
            img_np[h-s:h,0:s], img_np[h-s:h,w-s:w], 
            img_np[0:s, int(w/2)-25:int(w/2)+25]
        ]
        samples_cpu = np.concatenate([c.reshape(-1, 3) for c in corners])

        if HAS_GPU:
            samples_gpu = cp.asarray(samples_cpu)
            std_dev = float(cp.std(samples_gpu, axis=0).mean())
            mean_color = cp.asnumpy(cp.mean(samples_gpu, axis=0))
        else:
            std_dev = np.std(samples_cpu, axis=0).mean()
            mean_color = np.mean(samples_cpu, axis=0)
        
        if std_dev < 15.0: 
            if mean_color[0]>240 and mean_color[1]>240 and mean_color[2]>240: return "Isolated White", "Isolated subject on pure white."
            elif mean_color[0]<15 and mean_color[1]<15 and mean_color[2]<15: return "Isolated Black", "Isolated subject on black."
            else: return "Solid Color", "Studio shot with solid colored background."
        return "Complex", "Natural/Complex background."
    except: return "Complex", "Natural background."

# --- 4. HELPERS ---

def create_xmp_sidecar(path_without_ext, title, desc, keywords):
    try:
        rdf_keywords = "\n".join([f"<rdf:li>{k}</rdf:li>" for k in keywords])
        xmp = f"""<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'><rdf:Description rdf:about='' xmlns:dc='http://purl.org/dc/elements/1.1/'><dc:title><rdf:Alt><rdf:li xml:lang='x-default'>{title}</rdf:li></rdf:Alt></dc:title><dc:description><rdf:Alt><rdf:li xml:lang='x-default'>{desc}</rdf:li></rdf:Alt></dc:description><dc:subject><rdf:Bag>{rdf_keywords}</rdf:Bag></dc:subject></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end='w'?>"""
        with open(f"{path_without_ext}.xmp", "w", encoding="utf-8") as f: f.write(xmp)
        return f"{path_without_ext}.xmp"
    except: return None

def get_analysis_image_path(original_file_path):
    ext = os.path.splitext(original_file_path)[1].lower()
    temp_img_path = original_file_path + "_preview.jpg"
    if ext in ['.mp4', '.mov', '.avi', '.mkv']:
        try:
            cap = cv2.VideoCapture(original_file_path)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2 if total > 0 else 0)
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(temp_img_path, frame)
                return temp_img_path
        except: pass
    elif ext in ['.eps', '.ai']:
        try:
            args = ["gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=jpeg", "-dEPSCrop", "-r150", f"-sOutputFile={temp_img_path}", original_file_path]
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_img_path): return temp_img_path
        except: pass
    return original_file_path

# --- 5. MAIN OPTIMIZER ---

class StockPhotoOptimizer:
    def __init__(self):
        self.universal_blacklist = {"vector", "illustration", "drawing", "painting", "generated", "ai generated", "render", "3d", "artwork"}
        self.high_value_tech_tags = {"no people", "isolated", "white background", "copy space"}

    def analyze_technical_specs(self, image_path):
        specs = {"tags": [], "context_str": "", "blur_score": 0.0, "bg_type": "Complex"}
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                if w > h: specs["tags"].append("horizontal")
                elif h > w: specs["tags"].append("vertical")
                else: specs["tags"].append("square")

            # PANGGIL FUNGSI YANG NAMANYA SUDAH DISESUAIKAN (detect_blur)
            # Tapi logika di dalamnya sudah "Smart Bokeh + GPU"
            specs["blur_score"] = detect_blur(image_path)
            
            bg_type, bg_desc = analyze_background_type(image_path)
            specs["bg_type"] = bg_type

            parts = [f"Background Type: {bg_desc}."]
            if bg_type == "Isolated White": 
                specs["tags"].extend(["white background", "isolated"])
                parts.append("Isolated on white.")
            
            # > 25 = Sangat Tajam (Smart Logic)
            if specs["blur_score"] > 25: parts.append("Sharp focus.")
            elif specs["blur_score"] < 10: parts.append("Soft focus/Blur.")

            specs["context_str"] = " ".join(parts)
            return specs
        except Exception as e: return specs

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