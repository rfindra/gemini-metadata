#!/bin/bash

# Warna untuk tampilan terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}    GEMINI METADATA - AUTO INSTALLER V3   ${NC}"
echo -e "${GREEN}    (Fix for Ubuntu 24.04 Noble)          ${NC}"
echo -e "${BLUE}==========================================${NC}"

# 1. Update & Install System Dependencies
echo -e "${BLUE}[1/4] Menginstall sistem tools...${NC}"
sudo apt-get update -y

# [FIX] Mengganti libgl1-mesa-glx dengan libgl1
# [FIX] Menggunakan python3-full untuk mengatasi error venv/ensurepip
sudo apt-get install -y exiftool ghostscript ffmpeg libgl1 libglib2.0-0 python3-full python3-pip git

# 2. Setup Python Virtual Environment
echo -e "${BLUE}[2/4] Menyiapkan Virtual Environment...${NC}"
# Hapus venv lama yang rusak/gagal
if [ -d "venv" ]; then
    echo "   - Membersihkan instalasi gagal sebelumnya..."
    rm -rf venv
fi

# Membuat venv baru
python3 -m venv venv

# Cek apakah venv berhasil dibuat
if [ ! -f "venv/bin/activate" ]; then
    echo -e "\033[0;31m[ERROR] Gagal membuat Venv. Pastikan python3-full terinstall.\033[0m"
    exit 1
fi

source venv/bin/activate
echo "   - Venv berhasil dibuat dan diaktifkan."

# 3. Upgrade Pip & Install Python Packages
echo -e "${BLUE}[3/4] Menginstall Library Python & GPU Support...${NC}"
pip install --upgrade pip

# Install dependencies
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