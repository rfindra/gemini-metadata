# app.py
import os

# --- [TAMBAHKAN INI DI PALING ATAS] ---
# Membungkam warning gRPC fork yang berisik
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
os.environ["GRPC_VERBOSITY"] = "ERROR"
# --------------------------------------

import streamlit as st
from streamlit_option_menu import option_menu
from dotenv import load_dotenv
import streamlit as st
import os
from streamlit_option_menu import option_menu
from dotenv import load_dotenv

# Import Custom Modules
from database import init_db
from app_helpers import init_session_state
from views import (
    render_sidebar, render_gallery_page, 
    render_metadata_page, render_prompt_page, render_history_page
)

# 1. SETUP AWAL
load_dotenv(override=True)
init_db()

# 2. PAGE CONFIG
st.set_page_config(page_title="Gemini Studio", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 🎨 ULTRA-CLEAN UI/UX STYLING ENGINE
# ==========================================
st.markdown("""
<style>
    /* Import Font Modern: Inter (Standard UI Font) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Font Settings */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* --- LAYOUTING & SPACING --- */
    /* Memberikan ruang napas yang cukup di bagian atas dan bawah */
    .block-container {
        padding-top: 3.5rem; 
        padding-bottom: 5rem;
        max-width: 95% !important; 
    }

    /* --- NAVIGATION BAR CUSTOMIZATION --- */
    /* Membuat menu navigasi terlihat seperti tab modern */
    .nav-link {
        font-size: 14px !important;
        margin: 0px 5px !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    
    /* --- CARDS & CONTAINERS --- */
    /* Menghaluskan border dan memberikan efek depth minimalis */
    div[data-testid="stContainer"] {
        background-color: transparent;
        border-radius: 10px;
    }
    
    /* Styling khusus untuk kartu di Galeri agar hoverable */
    div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
        transition: box-shadow 0.2s ease, transform 0.2s ease;
    }
    
    /* --- BUTTONS --- */
    /* Tombol dengan radius sudut yang konsisten dan hover effect */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        font-size: 14px;
        height: 40px; 
        border: 1px solid rgba(128, 128, 128, 0.2);
        transition: all 0.2s ease-in-out;
    }
    
    /* Primary Button (Accent) */
    .stButton button[kind="primary"] {
        background-color: #FF4B4B;
        border: none;
        color: white;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #FF2B2B;
        box-shadow: 0 4px 12px rgba(255, 75, 75, 0.3);
        transform: translateY(-1px);
    }

    /* Secondary Button (Ghost) */
    .stButton button[kind="secondary"] {
        background-color: transparent;
    }
    .stButton button[kind="secondary"]:hover {
        border-color: #FF4B4B;
        color: #FF4B4B;
    }

    /* --- INPUT FIELDS --- */
    /* Input field yang lebih clean dan menyatu */
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px;
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #FF4B4B;
        box-shadow: 0 0 0 1px #FF4B4B;
    }

    /* --- SIDEBAR --- */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa; /* Light mode bg */
    }
    @media (prefers-color-scheme: dark) {
        section[data-testid="stSidebar"] {
            background-color: #0E1117; /* Dark mode bg */
            border-right: 1px solid rgba(255,255,255,0.05);
        }
    }

    /* --- EXPANDER --- */
    .streamlit-expanderHeader {
        font-weight: 500;
        border-radius: 8px;
    }
    
    /* --- METRICS --- */
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #888;
    }
    div[data-testid="stMetricValue"] {
        font-weight: 700;
    }

</style>
""", unsafe_allow_html=True)

# 3. INIT STATE
init_session_state()

# 4. NAVIGATION (Clean Tabs)
with st.container():
    selected_menu = option_menu(
        menu_title=None, 
        options=["Gallery", "Metadata Auto", "Prompt Architect", "History Log"], 
        icons=['images', 'robot', 'pencil-fill', 'archive'], 
        default_index=st.session_state['menu_index'],
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent", "margin-bottom": "20px"},
            "nav-link": {"font-size": "14px", "text-align": "center", "margin": "0px 5px", "padding": "10px"},
            "nav-link-selected": {"background-color": "#FF4B4B", "color": "white", "font-weight": "600"},
        }
    )

# 5. SIDEBAR & SETTINGS
settings = render_sidebar(selected_menu)

# 6. ROUTING
if selected_menu == "Gallery":
    render_gallery_page()

elif selected_menu == "Metadata Auto":
    render_metadata_page(settings)

elif selected_menu == "Prompt Architect":
    render_prompt_page(settings)

elif selected_menu == "History Log":
    render_history_page()