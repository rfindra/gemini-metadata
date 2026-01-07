#!/bin/bash
# Installer untuk Linux Native (Ubuntu/Debian/Fedora)

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}[Gemini Metadata] Linux Setup...${NC}"

# 1. Install System Deps
echo -e "${BLUE}-> Installing System Dependencies...${NC}"
if [ -f /etc/debian_version ]; then
    sudo apt-get update && sudo apt-get install -y exiftool ghostscript ffmpeg python3-venv git
elif [ -f /etc/fedora-release ]; then
    sudo dnf install -y perl-Image-ExifTool ghostscript ffmpeg
else
    echo "Distro not supported automatically. Install exiftool manually."
fi

# 2. Setup Python Venv
echo -e "${BLUE}-> Setting up Python Venv...${NC}"
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# 3. Install Pip Libs
echo -e "${BLUE}-> Installing Python Libraries...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 4. Config & Launcher
echo -e "${BLUE}-> Generating Config & Shortcut...${NC}"
DIR=$(pwd)
mkdir -p "$DIR/tmp_processing" "$DIR/output"

# Config JSON
cat <<EOF > user_settings.json
{ "temp_folder": "$DIR/tmp_processing", "output_folder": "$DIR/output" }
EOF

# Run Script
cat <<EOF > run.sh
#!/bin/bash
cd "$DIR"
source "$DIR/venv/bin/activate"
export PYTHONWARNINGS="ignore"
export GRPC_ENABLE_FORK_SUPPORT=0
streamlit run app.py --server.headless true
EOF
chmod +x run.sh

# Desktop Entry (Menu App)
mkdir -p ~/.local/share/applications
cat <<EOF > ~/.local/share/applications/gemini-metadata.desktop
[Desktop Entry]
Name=Gemini Metadata
Exec=$DIR/run.sh
Type=Application
Terminal=true
Icon=utilities-terminal
Categories=Utility;
EOF

echo -e "${GREEN}DONE! You can find 'Gemini Metadata' in your App Menu.${NC}"