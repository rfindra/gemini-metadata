#UPDATE
# app.py (Refactored)
import streamlit as st
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
st.set_page_config(page_title="Gemini Studio", page_icon="✨", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
    .block-container {
        padding-top: 5rem; 
        padding-bottom: 3rem;
    }
    .stButton button {
        width: 100%;
    }
    /* Opsional: Memberi sedikit jarak pada navigasi menu */
    div[data-testid="stVerticalBlock"] > div:has(ul.streamlit-option-menu) {
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 3. INIT STATE
init_session_state()

# 4. NAVIGATION
with st.container():
    selected_menu = option_menu(
        menu_title=None, 
        options=["Gallery", "Metadata Auto", "Prompt Architect", "History Log"], 
        icons=['images', 'camera', 'magic', 'clock'], 
        default_index=st.session_state['menu_index'],
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent", "margin-bottom": "10px"},
            "nav-link-selected": {"background-color": "#FF4B4B", "color": "white"},
        }
    )

# 5. SIDEBAR & SETTINGS
# Sidebar akan mengembalikan dict setting yang relevan (API Key, Model, dll)
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