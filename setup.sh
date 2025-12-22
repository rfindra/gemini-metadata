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
echo -e "${BLUE}[1/5] Menginstall sistem tools...${NC}"
sudo apt-get update -y
sudo apt-get install -y exiftool ghostscript ffmpeg libgl1 libglib2.0-0 python3-full python3-pip git

# 2. Setup Python Virtual Environment
echo -e "${BLUE}[2/5] Menyiapkan Virtual Environment...${NC}"
if [ -d "venv" ]; then
    echo "   - Membersihkan instalasi lama..."
    rm -rf venv
fi

python3 -m venv venv
if [ ! -f "venv/bin/activate" ]; then
    echo -e "\033[0;31m[ERROR] Gagal membuat Venv.\033[0m"
    exit 1
fi

source venv/bin/activate
echo "   - Venv berhasil dibuat dan diaktifkan."

# 3. Upgrade Pip & Install Python Packages
echo -e "${BLUE}[3/5] Menginstall Library Python & GPU Support...${NC}"
pip install --upgrade pip

# Memastikan semua library termasuk openai dan watchdog terpasang
if [ -f "requirements.txt" ]; then
    echo "   - Menginstall dari requirements.txt..."
    pip install -r requirements.txt
    pip install openai watchdog streamlit-option-menu # Double check
else
    echo "   - Menginstall library secara manual..."
    pip install streamlit opencv-python-headless pillow pandas python-dotenv \
                google-generativeai PyExifTool cupy-cuda12x streamlit-option-menu \
                openai watchdog openpyxl
fi

# 4. Membuat file Shortcut 'run.sh' (Headless & No Warnings)
echo -e "${BLUE}[4/5] Membuat shortcut eksekusi internal Linux...${NC}"
cat <<EOF > run.sh
#!/bin/bash
source $(pwd)/venv/bin/activate
export PYTHONWARNINGS="ignore"
cd $(pwd)
# Headless true mencegah error 'gio' di WSL
streamlit run app.py --server.headless true
EOF
chmod +x run.sh

# 5. Membuat Shortcut Startup Windows (Silent Mode)
echo -e "${BLUE}[5/5] Mengintegrasikan ke Startup Windows...${NC}"

# [FIX] Deteksi Nama Distro secara dinamis (karena $WSL_DISTRO_NAME sering kosong)
CURRENT_DISTRO=$(wsl.exe -l -v | grep -E '\*' | awk '{print $2}' | tr -d '\r')

# Fallback jika gagal deteksi
if [ -z "$CURRENT_DISTRO" ]; then
    CURRENT_DISTRO="Ubuntu-24.04"
fi

# Deteksi Username Windows secara akurat
WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
STARTUP_PATH="/mnt/c/Users/$WIN_USER/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"



if [ -d "$STARTUP_PATH" ]; then
    VBS_FILE="$STARTUP_PATH/StartGeminiMetadata.vbs"
    
    # Menulis file VBScript: 
    # Menggunakan perintah wsl.exe -d [NAMA_DISTRO] agar spesifik
    cat <<EOF > "$VBS_FILE"
Set WinScriptHost = CreateObject("WScript.Shell")
WinScriptHost.Run "wsl.exe -d $CURRENT_DISTRO -u $USER -- bash -c ""cd '$(pwd)' && ./run.sh""", 0
Set WinScriptHost = Nothing
EOF
    echo -e "   - Shortcut Windows Startup berhasil dibuat (Distro: $CURRENT_DISTRO)."
    echo -e "   - Lokasi: $VBS_FILE"
else
    echo -e "\033[0;33m[WARN] Folder Startup Windows tidak ditemukan di: $STARTUP_PATH\033[0m"
fi

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}✅ SETUP SELESAI! GEMINI METADATA SIAP.   ${NC}"
echo -e "Untuk memantau secara manual, ketik: ${BLUE}./run.sh${NC}"
echo -e "${GREEN}==========================================${NC}"
