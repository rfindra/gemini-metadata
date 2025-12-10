# ai_engine.py
import base64
from PIL import Image
import google.generativeai as genai
from openai import OpenAI
from utils import extract_json

def run_gemini_engine(model_name, api_key, image_path, prompt):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    try:
        img = Image.open(image_path)
        response = model.generate_content([prompt, img])
        return extract_json(response.text)
    except Exception as e: raise e

def run_openai_compatible_engine(model_name, api_key, base_url, image_path, prompt):
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        ],
        max_tokens=1000,
    )
    return extract_json(response.choices[0].message.content)