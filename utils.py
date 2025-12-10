# utils.py
import re
import json
import subprocess
from config import MODEL_PRICES

def clean_filename(title):
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    clean = clean.replace(" ", "-").strip().lower()
    return clean[:50]

def extract_json(text):
    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.MULTILINE)
    try: return json.loads(cleaned)
    except:
        start = cleaned.find("{")
        if start != -1:
            depth = 0
            for i, c in enumerate(cleaned[start:], start=start):
                if c == "{": depth += 1
                elif c == "}": depth -= 1
                if depth == 0:
                    try: return json.loads(cleaned[start:i+1])
                    except: continue
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