#!/bin/bash

# Warna untuk tampilan terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}    GEMINI METADATA - AUTO INSTALLER      ${NC}"
echo -e "${BLUE}==========================================${NC}"

# 1. Update & Install System Dependencies
echo -e "${BLUE}[1/4] Menginstall sistem tools (Sudo required)...${NC}"
sudo apt-get update -y
sudo apt-get install -y exiftool ghostscript ffmpeg libgl1-mesa-glx python3-venv python3-pip git

# 2. Setup Python Virtual Environment
echo -e "${BLUE}[2/4] Menyiapkan Virtual Environment...${NC}"
if [ -d "venv" ]; then
    echo "Menghapus venv lama..."
    rm -rf venv
fi
python3 -m venv venv
source venv/bin/activate

# 3. Upgrade Pip & Install Python Packages
echo -e "${BLUE}[3/4] Menginstall Library Python & GPU Support...${NC}"
pip install --upgrade pip
pip install streamlit opencv-python-headless pillow pandas python-dotenv google-generativeai PyExifTool cupy-cuda12x streamlit-option-menu

# 4. Membuat file Shortcut 'run.sh'
echo -e "${BLUE}[4/4] Membuat shortcut eksekusi...${NC}"
cat <<EOF > run.sh
#!/bin/bash
source venv/bin/activate
streamlit run app.py
EOF
chmod +x run.sh

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}✅ SETUP SELESAI! GEMINI METADATA SIAP.  ${NC}"
echo -e "Silakan jalankan dengan perintah: ${BLUE}./run.sh${NC}"
echo -e "${GREEN}==========================================${NC}"