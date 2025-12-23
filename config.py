import os
import sys
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# --- Path Configuration ---
BASE_WORK_DIR = os.path.join(os.getcwd(), "tmp_processing")

if not os.path.exists(BASE_WORK_DIR):
    try:
        os.makedirs(BASE_WORK_DIR)
    except Exception as e:
        print(f"Warning: Gagal membuat folder temp: {e}")

DEFAULT_INTERNAL_OUTPUT = os.path.join(os.getcwd(), "output")
DB_FILE = "gemini_history.db"

# [BARU] CENTRALIZED TOOL PATH (Refactor Poin 2)
# Deteksi path ExifTool sekali saja di sini agar modular dan rapi.
# Module lain tinggal import EXIFTOOL_PATH dari sini.
if os.name == 'nt':
    # Windows: Prioritaskan folder 'tools' lokal agar portable
    EXIFTOOL_PATH = os.path.join(os.getcwd(), "tools", "exiftool.exe")
else:
    # Linux/Mac: Asumsi terinstall di global PATH (install via apt/brew)
    EXIFTOOL_PATH = "exiftool"

# Validasi khusus Windows (Linux biasanya handle via 'which' di runtime)
if os.name == 'nt' and not os.path.exists(EXIFTOOL_PATH):
    print(f"⚠️ Warning: ExifTool binary not found at {EXIFTOOL_PATH}. Metadata writing might fail.")
    EXIFTOOL_PATH = None 

# Pricing Configuration (Estimasi per 1M token)
MODEL_PRICES = {
    "default": {"in": 0.10, "out": 0.40},
    "gemini": {"in": 0.00, "out": 0.00}, 
    "gemini-1.5-pro": {"in": 3.50, "out": 10.50},
    "gemma": {"in": 0.10, "out": 0.10},
    "groq": {"in": 0.00, "out": 0.00},
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "claude": {"in": 3.00, "out": 15.00}
}

# --- Prompt Presets (UPDATED WITH SAFETY & QUALITY) ---
PROMPT_PRESETS = {
    "Commercial (Standard) - BEST SELLER": {
        "title": "Stock Title: 5-15 words. Literal and precise.",
        "desc": "Visual Details: Lighting, Pose, Context, Vibe.",
        "full_instruction": """
        Role: Expert Stock Photographer & Metadata Specialist.
        Task: Analyze the image for Adobe Stock/Shutterstock.
        
        Requirements:
        1. SAFETY CHECK: Scan for trademarks/logos/faces. List found items or 'CLEAN'.
        2. QUALITY SCORE: Rate 1-10 (Commercial Appeal).
        3. METADATA GENERATION:
           - Title: Literal summary (Who, What, Where). Max 15 words.
           - Description: Do NOT repeat the title. Focus strictly on VISUAL DETAILS: Lighting (soft/harsh/natural), Angle (eye-level/aerial), Focus (sharp/bokeh), and Subject Action/Pose.
           - Keywords: 40-50 tags. Start with visible objects, then concepts.
        
        Output MUST be in valid JSON format:
        {
          "title": "...",
          "description": "...",
          "keywords": ["tag1", "tag2"],
          "category": "...",
          "safety_check": "...",
          "quality_score": 0.0
        }
        """
    },    "Microstock Specialist (Shutterstock/Adobe)": {
        "title": "Stock Title: 5-10 words describing Who, What, Where.",
        "desc": "Focus: Commercial demand and high-relevance keywords."
    },
    "Editorial (News/Journalism)": {
        "title": "Editorial Title: Factual Subject + Event + Location.",
        "desc": "Focus: Accuracy, news value, and strict factual description."
    },
    "Creative / Abstract / Backgrounds": {
        "title": "Abstract Title: Texture, pattern, or conceptual name.",
        "desc": "Focus: Artistic style, color gradients, and geometric shapes."
    },
    "Technical / Minimalist (Isolated)": {
        "title": "Technical Title: Object Name + View Angle + Background Type.",
        "desc": "Focus: Material texture, shadow detail, and technical clarity."
    }
}

# --- PROVIDERS CONFIGURATION (Sesuai Quota Anda) ---
PROVIDERS = {
    "Google Gemini (Native)": {
        "base_url": None,
        "env_var": "GOOGLE_API_KEY", 
        "models": {
            # Model High Quota (14.400 RPD) - Gunakan untuk Batch besar
            "Gemma 3 - 27B IT": "gemma-3-27b-it", 
            "Gemma 3 - 12B IT": "gemma-3-12b-it", 
            
            # Model Vision Terbaru (Kualitas Metadata Terbaik)
            "Gemini 2.0 Flash": "gemini-2.0-flash", 
            "Gemini 2.5 Flash": "gemini-2.5-flash",
            
            # Model Experimental (Sangat Cerdas tapi kuota sedikit)
            "Gemini 3 Flash Preview": "gemini-3-flash-preview", 
            "Gemini 3 Pro Preview": "gemini-3-pro-preview",     
            
            # Kuda Beban Stabil (Paling direkomendasikan untuk stock photo)
            "Gemini 1.5 Flash (Legacy)": "gemini-1.5-flash"
        }
    },
    "Groq Cloud": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY", 
        "models": {
            "Llama 3 70B (Versatile)": "llama3-70b-8192",
            "Llama 3 8B (Fast)": "llama3-8b-8192",
            "Mixtral 8x7b": "mixtral-8x7b-32768",
            "Gemma 2 9B IT": "gemma2-9b-it" 
        }
    },
    "OpenRouter (Aggregator)": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_var": "OPENROUTER_API_KEY", 
        "models": {
            "Anthropic Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet",
            "Mistral Large": "mistralai/mistral-large",
            "Auto Detect (Isi Custom ID)": "manual-entry"
        }
    },
    "OpenAI / Perplexity": {
        "base_url": "https://api.openai.com/v1",
        "env_var": "OPENAI_API_KEY", 
        "models": {
            "GPT-4o": "gpt-4o",
            "GPT-4o Mini": "gpt-4o-mini",
            "Auto Detect": "manual-entry"
        }
    }
}