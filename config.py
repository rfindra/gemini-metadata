import os
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Path Configuration
BASE_WORK_DIR = os.getcwd()
DEFAULT_INTERNAL_OUTPUT = os.path.join(BASE_WORK_DIR, "output")
DB_FILE = "gemini_history.db"

# Pricing Configuration (Estimasi)
MODEL_PRICES = {
    "default": {"in": 0.10, "out": 0.40},
    "gemini": {"in": 0.075, "out": 0.30},
    "gemma": {"in": 0.10, "out": 0.10},
    "groq": {"in": 0.00, "out": 0.00}, # Groq sering gratis/murah
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "claude": {"in": 3.00, "out": 15.00}
}

# Prompt Presets
PROMPT_PRESETS = {
    "Commercial (Standard) - BEST SELLER": {
        "title": "Commercial Style: Subject + Action + Context. Max 30 words. Clear, descriptive, and SEO-friendly.",
        "desc": "Visual Style: Lighting + Composition + Mood. Max 30 words. Professional tone, suitable for advertising."
    },
    "Editorial (News/Journalism)": {
        "title": "Editorial Style: Subject + Action + Location. Max 30 words. Strictly Factual. No opinions.",
        "desc": "Journalistic Description: Who, What, Where, When. Describe the scene objectively. No creative fluff."
    },
    "Creative / Abstract / Backgrounds": {
        "title": "Creative Style: Concept + Metaphor + Key Elements. Evocative language.",
        "desc": "Conceptual Description: Focus on Mood, Textures, Colors, Patterns, and Emotions. Artistic tone."
    },
    "Technical / Minimalist (Isolated)": {
        "title": "Punchy Style: Main Object + Main Characteristic. Max 15 words. Direct.",
        "desc": "Technical Description: Focus on isolation, white background details, and specific angles. Very brief."
    }
}

# --- PROVIDERS CONFIGURATION (DENGAN MAPPING API KEY) ---
PROVIDERS = {
    "Google Gemini (Native)": {
        "base_url": None,
        "env_var": "GOOGLE_API_KEY", # <--- Mapping ke .env
        "models": {
            "Gemma 3 - 27B (High Intelligence)": "gemma-3-27b-it", 
            "Gemma 3 - 12B (Balanced)": "gemma-3-12b-it",
            "Gemini 2.5 Flash (New Standard)": "gemini-2.5-flash",
            "Gemini 2.5 Flash Lite (Efficiency)": "gemini-2.5-flash-lite",
        }
    },
    "Groq Cloud": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY", # <--- Mapping ke .env
        "models": {
            "Llama 3 70B (Versatile)": "llama3-70b-8192",
            "Llama 3 8B (Fast)": "llama3-8b-8192",
            "Mixtral 8x7b": "mixtral-8x7b-32768"
        }
    },
    "OpenRouter (Aggregator)": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_var": "OPENROUTER_API_KEY", # <--- Mapping ke .env
        "models": {
            "Anthropic Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet",
            "Mistral Large": "mistralai/mistral-large",
            "Auto Detect (Isi Custom ID)": "manual-entry"
        }
    },
    "OpenAI / Perplexity": {
        "base_url": "https://api.openai.com/v1",
        "env_var": "OPENAI_API_KEY", # <--- Mapping ke .env
        "models": {
            "GPT-4o": "gpt-4o",
            "GPT-4o Mini": "gpt-4o-mini",
            "Auto Detect": "manual-entry"
        }
    }
}