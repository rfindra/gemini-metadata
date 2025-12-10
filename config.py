import os
from dotenv import load_dotenv

# Load Environment Variables dari file .env
load_dotenv()

# Ambil API Key Default (Jika ada)
DEFAULT_API_KEY = os.getenv("GEMINI_API_KEY")

# Path Configuration
BASE_WORK_DIR = os.getcwd()
DEFAULT_INTERNAL_OUTPUT = os.path.join(BASE_WORK_DIR, "output")
DB_FILE = "gemini_history.db"

# Pricing Configuration
MODEL_PRICES = {
    "gemini-2.5-flash": {"in": 0.075, "out": 0.30},
    "gemini-2.5-flash-lite": {"in": 0.0375, "out": 0.15},
    "gemma-3-27b": {"in": 0.20, "out": 0.20},
    "gemma-3-12b": {"in": 0.10, "out": 0.10},
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "claude-3-haiku": {"in": 0.25, "out": 1.25},
    "sonar": {"in": 1.0, "out": 1.0},
    "default": {"in": 0.10, "out": 0.40}
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

# Providers
PROVIDERS = {
    "Google Gemini (Native)": {
        "base_url": None,
        "models": {
            "Gemma 3 - 27B (High Intelligence)": "gemma-3-27b-it", 
            "Gemma 3 - 12B (Balanced)": "gemma-3-12b-it",
            "Gemini 2.5 Flash (New Standard)": "gemini-2.5-flash",
            "Gemini 2.5 Flash Lite (Efficiency)": "gemini-2.5-flash-lite",
        }
    },
    "OpenAI / OpenRouter / Perplexity": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": {
            "Auto Detect (Type Manual ID below)": "manual-entry"
        }
    }
}