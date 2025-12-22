import os
import cv2
import numpy as np
# Import fungsi dari image_ops Anda
from image_ops import detect_blur

# --- KONFIGURASI ---
# Ubah path Windows ke format WSL
FOLDER_PATH = "/mnt/d/Apps/Safari2025/skipped" 

def main():
    if not os.path.exists(FOLDER_PATH):
        print(f"❌ Folder tidak ditemukan: {FOLDER_PATH}")
        return

    print(f"📂 Memeriksa skor ketajaman di: {FOLDER_PATH}")
    print("-" * 50)
    print(f"{'FILENAME':<40} | {'SCORE':<10} | {'STATUS'}")
    print("-" * 50)

    files = [f for f in os.listdir(FOLDER_PATH) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if not files:
        print("⚠️ Tidak ada file gambar di folder ini.")
        return

    scores = []

    for filename in files:
        full_path = os.path.join(FOLDER_PATH, filename)
        
        # Cek Skor
        score = detect_blur(full_path, threshold=1.0) # Threshold 1.0 agar fungsi tetap jalan
        scores.append(score)
        
        # Status Text
        if score > 20: status = "Sangat Tajam"
        elif score > 10: status = "Normal"
        elif score > 5: status = "Agak Soft"
        else: status = "BLURRY"

        print(f"{filename[:38]:<40} | {score:<10.4f} | {status}")

    print("-" * 50)
    if scores:
        avg = sum(scores) / len(scores)
        min_s = min(scores)
        max_s = max(scores)
        print(f"📈 STATISTIK FOLDER:")
        print(f"   Rata-rata Skor : {avg:.4f}")
        print(f"   Skor Terendah  : {min_s:.4f}")
        print(f"   Skor Tertinggi : {max_s:.4f}")
        print("-" * 50)
        print(f"💡 REKOMENDASI SETTING:")
        print(f"   Set 'Min Sharpness' di aplikasi ke angka: {max(0.5, min_s - 2.0):.1f}")

if __name__ == "__main__":
    main()