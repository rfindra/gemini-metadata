# ai_engine.py
import base64
import json
import io
import typing_extensions as typing
from PIL import Image
import google.generativeai as genai
from openai import OpenAI
from utils import extract_json

# --- DEFINISI SCHEMA OUTPUT ---
# Ini digunakan untuk model yang support (Gemini 1.5/2.0)
class StockMetadata(typing.TypedDict):
    title: str
    description: str
    keywords: list[str]
    category: str
    safety_check: str
    quality_score: float

def run_gemini_engine(model_name, api_key, image_input, prompt):
    """
    Menjalankan Gemini/Gemma engine.
    Memiliki fitur FALLBACK: Jika JSON Mode gagal (error 400),
    otomatis beralih ke mode teks biasa + parsing manual.
    """
    genai.configure(api_key=api_key)
    
    # 1. Persiapkan Gambar (Load dari Path atau Memory)
    img_object = None
    try:
        if isinstance(image_input, str):
            img_object = Image.open(image_input)
        elif isinstance(image_input, bytes):
            img_object = Image.open(io.BytesIO(image_input))
        else:
            raise ValueError("Format gambar tidak dikenali.")
    except Exception as e:
        raise ValueError(f"Gagal membuka gambar: {str(e)}")

    # 2. STRATEGI UTAMA: Strict JSON Mode (Khusus Gemini)
    try:
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=StockMetadata
        )
        model = genai.GenerativeModel(model_name, generation_config=generation_config)
        response = model.generate_content([prompt, img_object])
        return json.loads(response.text)

    except Exception as e:
        # 3. STRATEGI CADANGAN: Fallback Mode (Untuk Gemma / Model Lain)
        err_msg = str(e)
        # Cek apakah errornya karena fitur JSON tidak support
        if "400" in err_msg or "JSON mode" in err_msg or "not enabled" in err_msg:
            print(f"⚠️ Model '{model_name}' tidak support Strict JSON. Beralih ke mode manual...")
            
            try:
                # Init ulang model TANPA config JSON yang ketat
                model_plain = genai.GenerativeModel(model_name)
                
                # Tambahkan penekanan ekstra di prompt
                fallback_prompt = prompt + "\n\nIMPORTANT: You must return ONLY raw JSON text. Do not wrap in markdown blocks."
                
                response = model_plain.generate_content([fallback_prompt, img_object])
                
                # Parsing manual menggunakan regex (mengandalkan utils.py)
                return extract_json(response.text)
            except Exception as e2:
                # Jika di mode manual masih error (misal Safety Filter), raise error asli
                print(f"❌ Fallback gagal: {e2}")
                raise e2
        
        # Jika error bukan karena JSON mode (misal API Key salah / Quota habis), lempar errornya
        raise e

def run_openai_compatible_engine(model_name, api_key, base_url, image_input, prompt):
    """
    Engine untuk OpenAI, Groq, OpenRouter, dll.
    """
    base64_image = ""
    try:
        if isinstance(image_input, str):
            with open(image_input, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        elif isinstance(image_input, bytes):
            base64_image = base64.b64encode(image_input).decode('utf-8')
        else:
             raise ValueError("Format gambar salah")

        client = OpenAI(api_key=api_key, base_url=base_url)
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        return extract_json(response.choices[0].message.content)

    except Exception as e:
        raise e