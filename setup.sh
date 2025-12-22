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

# [FIX] Mengganti libgl1-mesa-glx dengan libgl1
# [FIX] Menggunakan python3-full untuk mengatasi error venv/ensurepip
sudo apt-get install -y exiftool ghostscript ffmpeg libgl1 libglib2.0-0 python3-full python3-pip git

# 2. Setup Python Virtual Environment
echo -e "${BLUE}[2/5] Menyiapkan Virtual Environment...${NC}"
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
echo -e "${BLUE}[3/5] Menginstall Library Python & GPU Support...${NC}"
pip install --upgrade pip

# Install dependencies
pip install streamlit opencv-python-headless pillow pandas python-dotenv google-generativeai PyExifTool cupy-cuda12x streamlit-option-menu

# 4. Membuat file Shortcut 'run.sh'
echo -e "${BLUE}[4/5] Membuat shortcut eksekusi internal Linux...${NC}"
cat <<EOF > run.sh
#!/bin/bash
source $(pwd)/venv/bin/activate
cd $(pwd)
streamlit run app.py
EOF
chmod +x run.sh

# 5. Membuat Shortcut Startup Windows (Silent Mode)
echo -e "${BLUE}[5/5] Mengintegrasikan ke Startup Windows...${NC}"

# Deteksi Username Windows
WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
STARTUP_PATH="/mnt/c/Users/$WIN_USER/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"

if [ -d "$STARTUP_PATH" ]; then
    VBS_FILE="$STARTUP_PATH/StartGeminiMetadata.vbs"
    # Menulis file VBScript agar jalan tanpa jendela CMD (Silent)
    cat <<EOF > "$VBS_FILE"
Set WinScriptHost = CreateObject("WScript.Shell")
WinScriptHost.Run "wsl.exe -d $WSL_DISTRO_NAME -u $USER -- bash -c 'cd $(pwd) && ./run.sh'", 0
Set WinScriptHost = Nothing
EOF
    echo -e "   - Shortcut Windows Startup berhasil dibuat."
    echo -e "   - Lokasi: $VBS_FILE"
else
    echo -e "\033[0;33m[WARN] Folder Startup Windows tidak terdeteksi. Shortcut dilewati.\033[0m"
fi

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}✅ SETUP SELESAI! GEMINI METADATA SIAP.   ${NC}"
echo -e "Aplikasi akan otomatis berjalan saat Windows startup."
echo -e "Untuk menjalankan manual, ketik: ${BLUE}./run.sh${NC}"
echo -e "${GREEN}==========================================${NC}"