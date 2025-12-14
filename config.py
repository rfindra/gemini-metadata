import os
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# --- Path Configuration (UPDATED) ---
# Menggunakan folder khusus 'tmp_processing' agar file sampah tidak mengotori root
BASE_WORK_DIR = os.path.join(os.getcwd(), "tmp_processing")

# Buat folder tmp_processing otomatis jika belum ada
if not os.path.exists(BASE_WORK_DIR):
    try:
        os.makedirs(BASE_WORK_DIR)
    except Exception as e:
        print(f"Warning: Gagal membuat folder temp: {e}")

# Folder output tetap di root agar mudah ditemukan user
DEFAULT_INTERNAL_OUTPUT = os.path.join(os.getcwd(), "output")

# Database tetap di root
DB_FILE = "gemini_history.db"

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

# Prompt Presets
PROMPT_PRESETS = {
    "Commercial (Standard) - BEST SELLER": {
        "title": "Commercial Title: Subject + Main Action + Specific Context. Max 15 words. Literal and precise.",
        "desc": "Atmosphere Description: Describe the lighting, mood, environment, background, and color palette. Do NOT repeat the subject action. Max 30 words."
    },
    "Microstock Specialist (Shutterstock/Adobe)": {
        "title": "Stock Title: 5-10 words describing exactly WHAT is in the image (Who, What, Where). No flowery language.",
        "desc": "Stock Details: Describe the surroundings, time of day, lighting quality (e.g., soft light, golden hour), and emotional tone. Do NOT repeat the title."
    },
    "Editorial (News/Journalism)": {
        "title": "Editorial Title: Subject + Event/Action + Location + Date (Generic). Factual.",
        "desc": "Contextual Description: Describe the background scene, crowd atmosphere, and environmental details strictly factually."
    },
    "Creative / Abstract / Backgrounds": {
        "title": "Abstract Title: The main concept, texture, or pattern name.",
        "desc": "Visual Description: Describe the color gradients, artistic style, geometric shapes, and feelings invoked."
    },
    "Technical / Minimalist (Isolated)": {
        "title": "Technical Title: Main Object Name + View Angle (e.g., Top View) + Background (e.g., White Background).",
        "desc": "Technical Details: Describe the isolation technique, shadows, material texture, and clarity."
    }
}

# --- PROVIDERS CONFIGURATION ---
PROVIDERS = {
    "Google Gemini (Native)": {
        "base_url": None,
        "env_var": "GOOGLE_API_KEY", 
        "models": {
            "Gemma 3 - 27B IT (High Intelligence)": "gemma-3-27b-it",
            "Gemma 3 - 12B IT (Balanced)": "gemma-3-12b-it",
            "Gemma 3 - 4B IT (Speed/Edge)": "gemma-3-4b-it",
            "Gemini 2.0 Flash Exp (Newest)": "gemini-2.0-flash-exp",
            "Gemini Exp 1206 (Experimental)": "gemini-exp-1206",
            "Gemini 1.5 Flash (Stable)": "gemini-1.5-flash",
            "Gemini 1.5 Pro (Reasoning)": "gemini-1.5-pro",
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