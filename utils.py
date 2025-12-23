import re
import json
import subprocess
import os # Tambahkan os
from config import MODEL_PRICES

def clean_filename(title):
    # Hapus karakter aneh file system
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    # Ganti spasi dengan underscore atau dash agar lebih aman di URL/Web
    clean = clean.replace(" ", "_").strip().lower()
    # Batasi panjang agar tidak error di Windows (Max path limit)
    return clean[:100]

def extract_json(text):
    """
    Pembersih JSON yang lebih agresif untuk menangani output AI yang 'kotor'.
    """
    text = text.strip()
    
    # 1. Coba parsing langsung (Best Case)
    try: return json.loads(text)
    except: pass

    # 2. Hapus Markdown Code Blocks (```json ... ```)
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except: pass

    # 3. Cari kurung kurawal terluar secara manual (Fallback terakhir)
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            json_str = text[start : end + 1]
            return json.loads(json_str)
    except:
        pass
        
    # 4. Jika gagal total, return dict kosong agar aplikasi tidak crash
    return {}

def calculate_cost(model_name, tokens_in, tokens_out):
    price = MODEL_PRICES["default"]
    for key in MODEL_PRICES:
        if key in model_name.lower():
            price = MODEL_PRICES[key]
            break
    cost = (tokens_in / 1_000_000 * price["in"]) + (tokens_out / 1_000_000 * price["out"])
    return cost

def select_folder_from_wsl(dialog_title="Pilih Folder"):
    # (Kode tetap sama seperti sebelumnya)
    try:
        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        $f = New-Object System.Windows.Forms.FolderBrowserDialog
        $f.Description = '{dialog_title}'
        $f.ShowNewFolderButton = $true
        if ($f.ShowDialog() -eq 'OK') {{
            Write-Output $f.SelectedPath
        }}
        """
        cmd = ["powershell.exe", "-Command", ps_script]
        windows_path = subprocess.check_output(cmd).decode().strip()
        if not windows_path: return None
        windows_path = windows_path.strip()
        drive_letter = windows_path[0].lower()
        path_tail = windows_path[2:].replace("\\", "/")
        wsl_path = f"/mnt/{drive_letter}{path_tail}"
        return wsl_path
    except Exception as e:
        return None

def construct_prompt_template(title_rule, desc_rule):
    # (Kode tetap sama)
    return f"""
    Analyze for Commercial Stock (Photo/Video/Vector). Return strictly JSON.
    SYSTEM CONTEXT (Visual Facts): {{context_injection}}
    Structure: 
    {{
        "title": "{title_rule}", 
        "description": "{desc_rule}", 
        "keywords": "comma separated string of 50 keywords",
        "category": "Pick ONE: People, Nature, Business, Food, Travel, Architecture, Animals, Lifestyle, Technology, Abstract"
    }}
    INSTRUCTIONS:
    1. Title: Focus on WHAT is happening. Must be under 200 characters.
    2. Description: Focus on HOW it looks (aesthetic/technical). Must be under 200 characters.
    3. Keywords: Start with VISIBLE OBJECTS, then CONCEPTS. Include 'no people' if applicable.
    4. No markdown. Only JSON.
    """