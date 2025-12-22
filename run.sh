#!/bin/bash
source /home/indra/gemini-metadata/venv/bin/activate
export PYTHONWARNINGS="ignore"
cd /home/indra/gemini-metadata
# Headless true agar tidak error saat dijalankan via VBScript/Startup
streamlit run app.py --server.headless true
