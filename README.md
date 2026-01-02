# ✨ Gemini-Metadata: AI-Powered Stock Media Automator (V4)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red) ![CUDA](https://img.shields.io/badge/GPU-NVIDIA%20CUDA%2013.x-green) ![License](https://img.shields.io/badge/License-MIT-purple)

**Gemini-Metadata** adalah asisten otomasi cerdas untuk kontributor *stock media* (Photo, Video, & Vector). Versi terbaru ini menghadirkan antarmuka **Modern & Clean**, arsitektur kode modular, serta dukungan penuh untuk **Rate Limiting** dan **GPU Acceleration** (CUDA 13.x) demi performa maksimal tanpa error API.

---

## 🚀 Fitur Baru & Utama

### 🎨 Modern UI & Experience
* **Clean Dashboard**: Desain antarmuka baru menggunakan font *Inter*, layout *card* minimalis, dan *spacing* yang lega.
* **Smart Gallery**: Galeri interaktif dengan fitur pencarian, paginasi, dan tombol *Quick Edit* (Popover) yang rapi.
* **Hardware Status Badge**: Indikator *real-time* di sidebar untuk memantau status akselerasi (NVIDIA GPU / Intel / Apple Silicon / CPU Mode).

### ⚡ Performa & Logika
* **Smart Rate Limiter**: Kontrol penuh atas *Threads* dan *Delay* (detik) untuk mematuhi batas kuota API (misal: 30 RPM pada model Gemma-3), mencegah error `429 Too Many Requests`.
* **Batch Processing Core**: Fokus pada pemrosesan massal yang stabil dengan *limit slider* otomatis (Maksimal = Total File).
* **GPU Accelerated**: Deteksi *blur* super cepat menggunakan **CuPy** (mendukung driver NVIDIA terbaru CUDA 13.x).
* **Clean Logs**: Terminal bebas dari *spam* warning gRPC/Fork berkat optimasi *environment variables*.

### 🧠 Kemampuan Inti
* **Multimodal AI Analysis**: Integrasi Google Gemini (2.0 Flash, 1.5 Pro) untuk analisis visual mendalam.
* **Duplicate Filter**: Algoritma *dHash* untuk membuang foto duplikat/burst sebelum diproses (hemat biaya API).
* **Universal Metadata**: Menulis metadata (Title, Desc, Keywords) langsung ke file (EXIF/IPTC/XMP) via ExifTool.
* **Agency Reports**: Ekspor CSV otomatis untuk Adobe Stock, Shutterstock, dan Getty Images.

---

## 🛠️ Arsitektur Teknologi (Refactored)

Kode kini terorganisir secara modular untuk kemudahan pemeliharaan:

* **`app.py`**: Router utama dan konfigurasi CSS/Global State.
* **`views.py`**: Menangani seluruh tampilan antarmuka (UI), Sidebar, Galeri, dan Widget.
* **`app_helpers.py`**: Logika *backend* jembatan antara UI dan pemrosesan data.
* **`processor.py`**: Otak pemrosesan gambar dan komunikasi ke AI Engine.
* **`image_ops.py`**: Operasi citra tingkat rendah (Hashing, Blur Detection via GPU).
* **`database.py`**: Manajemen SQLite untuk riwayat dan log.

---

## 📥 Panduan Instalasi (Ubuntu 24.04 / WSL2)

### 1. Prasyarat Sistem
* **Windows 10/11** dengan driver NVIDIA terbaru (mendukung CUDA 13.x).
* **WSL2** terinstall.

### 2. Setup Lingkungan (Terminal Ubuntu)

Jalankan perintah berikut satu per satu:

```bash
# 1. Update sistem
sudo apt update && sudo apt upgrade -y

# 2. Clone Repositori
git clone [https://github.com/USERNAME/gemini-metadata.git](https://github.com/USERNAME/gemini-metadata.git)
cd gemini-metadata

# 3. Jalankan Auto-Installer (V4)
# Script ini akan menginstall Python, Venv, ExifTool, dan Library CUDA secara otomatis.
chmod +x setup.sh
./setup.sh
3. Konfigurasi API Key
Buat file .env dan masukkan API Key Google Gemini Anda:

Bash

nano .env
Isi dengan:

Ini, TOML

GOOGLE_API_KEY=AIzaSy... (Paste API Key Anda di sini)
Simpan dengan Ctrl+O -> Enter -> Ctrl+X.

🖥️ Cara Penggunaan
1. Menjalankan Aplikasi
Gunakan shortcut yang telah dibuat oleh installer:

Bash

./run.sh
Buka browser di: http://localhost:8501

2. Memproses File (Metadata Auto)
Buka menu Metadata Auto di sidebar.

Pilih Folder: Gunakan tombol "Browse" (akan membuka dialog Windows asli).

Atur Konfigurasi Batch (Sidebar):

Threads: Set ke 1 jika menggunakan model gratisan (untuk menghindari limit).

Delay: Set ke 2.5 detik agar aman (di bawah 30 RPM).

Scan Duplicates (Opsional): Hapus file kembar sebelum diproses.

Start Processing: Klik tombol roket untuk memulai.

3. Review & Edit (Smart Gallery)
Buka menu Gallery.

Gunakan Search Bar untuk mencari file tertentu.

Klik tombol Edit (✏️) pada kartu gambar untuk merevisi metadata menggunakan AI (misal: "Ubah ke Bahasa Indonesia").

Gunakan Bulk Actions untuk mengedit banyak file sekaligus.

📂 Struktur Folder Proyek
Plaintext

gemini-metadata/
├── app.py              # Main Entry Point & Router
├── views.py            # UI Components (Sidebar, Pages, Cards)
├── app_helpers.py      # Backend Logic & Helper Functions
├── processor.py        # Core Image Processing Pipeline
├── image_ops.py        # GPU Acceleration & Image Algo
├── database.py         # SQLite Handler
├── ai_engine.py        # LLM Interface
├── config.py           # Constants & Settings
├── utils.py            # Utility Tools
├── setup.sh            # Auto Installer Script
├── run.sh              # App Launcher
└── requirements.txt    # Python Dependencies
⚠️ Catatan Penting
GPU Mode: Jika Anda melihat [INFO] NVIDIA GPU Detected, berarti akselerasi aktif. Jika [WARN], pastikan driver NVIDIA di Windows sudah terupdate.

API Quota: Pantau penggunaan API Anda di Google AI Studio. Gunakan fitur Delay di aplikasi untuk menghindari temporary ban.

Developed with ❤️ for Stock Contributors.