import cv2
import numpy as np
import os
import subprocess
from PIL import Image, ImageStat

# --- 1. GPU AUTO-DETECT ---
try:
    import cupy as cp
    HAS_GPU = True
    print("🚀 NVIDIA GPU Detected: Acceleration Enabled")
except ImportError:
    import numpy as cp
    HAS_GPU = False
    print("⚠️ GPU Not Found: Running on CPU mode")

# --- 2. SPEED OPTIMIZED BLUR DETECTION ---

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

# --- 3. BACKGROUND SORTING LOGIC (SOLID VS COMPLEX) ---

def analyze_background_type(image_path):
    """
    Membedakan:
    1. Isolated White (RGB > 240, Variance Rendah)
    2. Isolated Black (RGB < 15, Variance Rendah)
    3. Solid Color (Warna Lain, Variance Rendah) -> INI YANG ANDA CARI
    4. Complex (Variance Tinggi)
    """
    try:
        # Load pakai PIL agar akurasi warna RGB lebih baik drpd OpenCV
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            # Resize kecil (100px) sangat cukup untuk cek warna & hemat GPU
            img.thumbnail((100, 100)) 
            img_np = np.array(img)
            
        h, w, _ = img_np.shape
        s = 15 # Ukuran sample sudut

        # Ambil sampel dari 4 sudut + Bagian Atas Tengah (Biasanya background)
        # Kita hindari tengah-tengah persis karena disitu biasanya ada objek
        corners = [
            img_np[0:s, 0:s],           # Kiri Atas
            img_np[0:s, w-s:w],         # Kanan Atas
            img_np[h-s:h, 0:s],         # Kiri Bawah
            img_np[h-s:h, w-s:w],       # Kanan Bawah
            img_np[0:s, int(w/2)-5:int(w/2)+5] # Atas Tengah
        ]
        
        # Gabung semua sampel pixel
        samples_cpu = np.concatenate([c.reshape(-1, 3) for c in corners])

        # Hitung Statistik (Pakai GPU jika ada)
        if HAS_GPU:
            samples_gpu = cp.asarray(samples_cpu)
            # Standar Deviasi: Semakin kecil = Semakin seragam (Solid)
            std_dev = float(cp.std(samples_gpu, axis=0).mean())
            # Rata-rata Warna
            mean_color = cp.asnumpy(cp.mean(samples_gpu, axis=0))
        else:
            std_dev = np.std(samples_cpu, axis=0).mean()
            mean_color = np.mean(samples_cpu, axis=0)
        
        # LOGIKA SORTIR
        # Toleransi 20.0: Angka ini menentukan "toleransi keramaian".
        # < 20.0 = Background Solid/Bersih
        # > 20.0 = Background Ramai/Kompleks
        if std_dev < 20.0: 
            if mean_color[0]>240 and mean_color[1]>240 and mean_color[2]>240: 
                return "Isolated White", "Isolated on white background"
            elif mean_color[0]<20 and mean_color[1]<20 and mean_color[2]<20: 
                return "Isolated Black", "Isolated on black background"
            else: 
                # Ini akan menangkap Background Merah, Biru, Hijau, Abu-abu polos
                return "Solid Color", "Studio shot with solid colored background"
        
        return "Complex", "Natural environment background"
    except: 
        return "Complex", "Natural background"

# --- 4. HELPERS (TETAP) ---

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

            # Analisis Blur
            specs["blur_score"] = detect_blur(image_path)
            
            # Analisis Background (Solid/Complex)
            bg_type, bg_desc = analyze_background_type(image_path)
            specs["bg_type"] = bg_type

            # Menyusun Prompt Context agar AI tau ini Solid/Complex
            parts = [f"Background Style: {bg_desc}."]
            
            if bg_type == "Isolated White": 
                specs["tags"].extend(["white background", "isolated"])
            elif bg_type == "Isolated Black": 
                specs["tags"].extend(["black background", "isolated"])
            elif bg_type == "Solid Color":
                # Keyword penting untuk foto solid
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

# ... (Kode sebelumnya tetap sama, paste ini di paling bawah) ...

# --- 6. SIMILARITY CHECKER (dHash) ---

def compute_dhash(image_path, hash_size=8):
    """
    Menghitung 'Sidik Jari' (Hash) gambar.
    Tahan terhadap perubahan ukuran, format, dan sedikit warna.
    """
    try:
        # 1. Convert ke Grayscale
        # 2. Resize ke (hash_size + 1, hash_size) -> misal 9x8
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None: return None
        
        resized = cv2.resize(img, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        
        # 3. Bandingkan pixel bertetangga
        diff = resized[:, 1:] > resized[:, :-1]
        
        # 4. Convert ke Integer (64-bit hash)
        return sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])
    except:
        return None

def calculate_similarity_percentage(hash1, hash2):
    """
    Menghitung persentase kemiripan antara dua hash.
    Output: 0.0 sampai 100.0
    """
    if hash1 is None or hash2 is None: return 0.0
    
    # Hitung Hamming Distance (Beda berapa bit?)
    # XOR hash1 dan hash2, lalu hitung jumlah bit '1'
    hamming_dist = bin(int(hash1) ^ int(hash2)).count('1')
    
    # Total bit adalah 64 (karena 8x8)
    # Similarity = (64 - beda) / 64 * 100
    similarity = (64 - hamming_dist) / 64 * 100
    return similarity