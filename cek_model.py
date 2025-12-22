import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API Key dari file .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: API Key tidak ditemukan di file .env")
else:
    genai.configure(api_key=api_key)

    print("--- DAFTAR MODEL YANG TERSEDIA ---")
    try:
        for m in genai.list_models():
            # Hanya tampilkan model yang mendukung generateContent (untuk teks/gambar)
            if 'generateContent' in m.supported_generation_methods:
                # m.name biasanya berformat 'models/gemini-1.5-flash'
                # ID yang digunakan di config adalah bagian belakangnya saja
                model_id = m.name.split('/')[-1]
                print(f"Nama: {m.display_name}")
                print(f"ID  : {model_id}")
                print(f"Metode yang didukung: {m.supported_generation_methods}")
                print("-" * 30)
    except Exception as e:
        print(f"Gagal mengambil daftar model: {e}")