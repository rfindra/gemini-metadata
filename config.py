import os
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
        "desc": "Analysis: Quality Score 1-10 & IP Safety Check (Logos/Trademarks).",
        "full_instruction": """
        Role: Expert Stock Photographer & Intellectual Property Lawyer.
        Task: Analyze the image for premium commercial stock agencies (Adobe Stock/Shutterstock).
        
        Requirements:
        1. SAFETY CHECK: Scan for visible trademarks, brand logos, copyrighted art, or recognizable private property.
           - If found, list them in 'safety_check'.
           - If none, write 'CLEAN'.
        2. QUALITY SCORE: Rate the commercial appeal (1-10) based on composition, lighting, and marketability.
        3. METADATA: Provide a literal Title (max 15 words) and 40-50 Keywords sorted by relevance.
        
        Output MUST be in valid JSON format:
        {
          "title": "...",
          "description": "...",
          "keywords": ["keyword1", "keyword2"],
          "category": "...",
          "safety_check": "...",
          "quality_score": 0.0
        }
        """
    },
    "Microstock Specialist (Shutterstock/Adobe)": {
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
            "Gemma 3 - 27B IT": "gemma-3-27b-it", # Perbaikan: Tambah -it
            "Gemma 3 - 12B IT": "gemma-3-12b-it", # Perbaikan: Tambah -it
            
            # Model Vision Terbaru (Kualitas Metadata Terbaik)
            "Gemini 2.0 Flash": "gemini-2.0-flash", 
            "Gemini 2.5 Flash": "gemini-2.5-flash",
            
            # Model Experimental (Sangat Cerdas tapi kuota sedikit)
            "Gemini 3 Flash Preview": "gemini-3-flash-preview", # Perbaikan: Tambah -preview
            "Gemini 3 Pro Preview": "gemini-3-pro-preview",     # Perbaikan: Tambah -preview
            
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