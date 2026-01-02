#!/bin/bash

# Warna untuk tampilan terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}    GEMINI METADATA - AUTO INSTALLER V4   ${NC}"
echo -e "${GREEN}    (CUDA 13.x Edition)                   ${NC}"
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

if [ -f "requirements.txt" ]; then
    echo "   - Menginstall dari requirements.txt..."
    pip install -r requirements.txt
else
    echo -e "\033[0;31m[ERROR] requirements.txt tidak ditemukan!\033[0m"
    exit 1
fi

# 4. Membuat file Shortcut 'run.sh' (Updated with Clean Logs Env)
echo -e "${BLUE}[4/5] Membuat shortcut eksekusi internal Linux...${NC}"
cat <<EOF > run.sh
#!/bin/bash
source $(pwd)/venv/bin/activate

# Suppress Python Warnings
export PYTHONWARNINGS="ignore"

# Suppress gRPC Fork/Noise Logs (Fix Terminal Spam)
export GRPC_ENABLE_FORK_SUPPORT=0
export GRPC_VERBOSITY=ERROR

cd $(pwd)
# Headless true agar tidak error saat dijalankan via VBScript/Startup
streamlit run app.py --server.headless true
EOF
chmod +x run.sh

# 5. Membuat Shortcut Startup Windows (Silent Mode)
echo -e "${BLUE}[5/5] Mengintegrasikan ke Startup Windows...${NC}"

# Deteksi Distro WSL saat ini
CURRENT_DISTRO=$(wsl.exe -l -v | grep -E '\*' | awk '{print $2}' | tr -d '\r')
if [ -z "$CURRENT_DISTRO" ]; then CURRENT_DISTRO="Ubuntu-24.04"; fi

# Deteksi User Windows
WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
STARTUP_PATH="/mnt/c/Users/$WIN_USER/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"

if [ -d "$STARTUP_PATH" ]; then
    VBS_FILE="$STARTUP_PATH/StartGeminiMetadata.vbs"
    CURRENT_DIR=$(pwd)

    # Generate VBScript
    cat <<EOF > "$VBS_FILE"
Set WinScriptHost = CreateObject("WScript.Shell")
' Parameter 0 menjalankan script tanpa memunculkan jendela hitam CMD
WinScriptHost.Run "wsl.exe -d $CURRENT_DISTRO -u $USER -- bash -c ""cd '$CURRENT_DIR' && ./run.sh""", 0
Set WinScriptHost = Nothing
EOF
    echo -e "   - Shortcut Windows Startup berhasil dibuat (Distro: $CURRENT_DISTRO)."
else
    echo -e "\033[0;33m[WARN] Folder Startup Windows tidak ditemukan.\033[0m"
fi

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}✅ SETUP SELESAI! GEMINI METADATA SIAP.   ${NC}"
echo -e "Aplikasi akan otomatis aktif saat Windows menyala."
echo -e "Untuk tes sekarang, jalankan: ${BLUE}./run.sh${NC}"