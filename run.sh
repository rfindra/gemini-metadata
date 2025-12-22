#!/bin/bash
source /home/indra/gemini-metadata/venv/bin/activate
export PYTHONWARNINGS="ignore"
cd /home/indra/gemini-metadata
# Headless true mencegah error 'gio' di WSL
streamlit run app.py --server.headless true
