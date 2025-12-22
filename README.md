# ✨ Gemini-Metadata: AI-Powered Stock Media Automator

**Gemini-Metadata** adalah asisten otomasi cerdas yang dirancang khusus untuk kontributor *stock media* (Photo, Video, & Vector). Alat ini menggabungkan kekuatan **Vision AI** terkini dengan teknik pemrosesan citra tingkat tinggi untuk menghasilkan metadata yang akurat, relevan, dan siap jual secara otomatis.

---

## 🚀 Fitur Utama

* **Multimodal AI Analysis**: Integrasi dengan Google Gemini (3 Flash, 2.5 Flash, 1.5 Pro) untuk analisis konten visual secara mendalam.
* **Smart Duplication Filter**: Menggunakan algoritma **dHash (Difference Hashing)** + **Color Signature** untuk mendeteksi foto *burst*, mencegah pemborosan kuota API.
* **GPU Accelerated Processing**: Deteksi ketajaman (*blur detection*) berbasis **FFT (Fast Fourier Transform)** yang diakselerasi oleh **NVIDIA GPU (via CuPy)**.
* **Universal Metadata Writing**: Penulisan otomatis Title, Description, dan Keywords ke dalam tag **EXIF, IPTC, dan XMP** menggunakan ExifTool.
* **WSL-Windows Bridge**: Solusi unik menggunakan *PowerShell bridge* agar pengguna Linux (WSL) tetap bisa menggunakan *Folder Picker* asli Windows.
* **Agency Ready Reports**: Ekspor otomatis ke format CSV yang kompatibel dengan **Adobe Stock, Shutterstock, dan Getty Images**.

---

## 🛠️ Arsitektur Teknologi

* **Frontend**: Streamlit (Web-based Dashboard)
* **Intelligence**: Google Gemini API, OpenAI SDK
* **Database**: SQLite (History & Prompt Logs)
* **Image Core**: OpenCV, Pillow, CuPy (GPU Acceleration)
* **Metadata Core**: PyExifTool (ExifTool Wrapper)

---

## 📥 Panduan Instalasi Sistem (Step-by-Step)

Ikuti langkah-langkah di bawah ini untuk menyiapkan lingkungan **Ubuntu 24.04.3 LTS** di dalam Windows menggunakan **WSL2**.

### 1. Instalasi WSL (Windows Subsystem for Linux)
Buka **PowerShell** (Run as Administrator), lalu jalankan perintah:
```powershell
wsl --install
Catatan: Jika sudah terinstall, pastikan versinya terbaru dengan perintah wsl --update.

2. Instalasi Ubuntu 24.04.3 LTS
Gunakan distro Ubuntu Noble terbaru untuk stabilitas maksimal:

PowerShell

wsl --install -d Ubuntu-24.04
Setelah selesai, jendela terminal akan terbuka. Masukkan Username dan Password baru Anda.

3. Pembaruan Sistem (Update & Upgrade)
Di dalam terminal Ubuntu, jalankan perintah berikut untuk memastikan semua library sistem terbaru:

Bash

sudo apt update && sudo apt upgrade -y
4. Dukungan GPU NVIDIA (CUDA)
Aplikasi ini mendukung akselerasi GPU untuk pemrosesan gambar.

Langkah: Cukup install driver NVIDIA terbaru (Game Ready atau Studio Driver) di Windows Anda.

Verifikasi: Di terminal Ubuntu, ketik nvidia-smi. Jika muncul tabel informasi GPU, maka dukungan GPU sudah aktif.

⚙️ Setup & Instalasi Proyek
1. Clone Repositori
Bash

git clone [https://github.com/USERNAME/gemini-metadata.git](https://github.com/USERNAME/gemini-metadata.git)
cd gemini-metadata
2. Jalankan Auto-Installer
Gunakan script setup.sh yang sudah disediakan untuk menginstall semua dependensi (Python, Venv, ExifTool, FFmpeg, dll) secara otomatis:

Bash

chmod +x setup.sh
./setup.sh
3. Konfigurasi API Key
Buat file .env di folder utama proyek:

Bash

nano .env
Masukkan API Key Anda di dalamnya:

Plaintext

GOOGLE_API_KEY=AIzaSy... (masukkan key Anda di sini)
Tekan Ctrl+O, Enter, lalu Ctrl+X untuk menyimpan.

🖥️ Cara Penggunaan
Jalankan Aplikasi:

Bash

./run.sh
Buka Browser: Akses alamat http://localhost:8501.

Pilih Folder: Gunakan tombol Browse untuk memilih folder foto di Windows Anda.

Scan Duplikasi: Klik Scan for Duplicates untuk membersihkan file yang serupa (hemat kuota).

Start Processing: Tekan tombol proses dan AI akan mulai mengisi metadata ke file Anda.

📂 Struktur Proyek
app.py: Antarmuka utama Streamlit.

processor.py: Logika utama alur pemrosesan file.

image_ops.py: Algoritma hashing, deteksi blur, dan optimasi GPU.

ai_engine.py: Driver komunikasi API AI.

database.py: Manajemen riwayat proses (SQLite).

utils.py: Helper functions & WSL Windows Bridge.

🖋️ Catatan Pengembangan
Alat ini dikembangkan untuk meningkatkan efisiensi tugas administratif fotografer profesional melalui otomasi AI, memastikan produktivitas maksimal tanpa mengorbankan kualitas metadata.

Author: Indra (PNS & Tech Enthusiast) Version: 3.1.0 (Stable)


---

**Cara Menyimpan:**
1. Buka terminal di folder proyek Anda.
2. Ketik `nano README.md`.
3. Tempel (Paste) teks di atas.
4. Simpan dengan `Ctrl+O`, `Enter`, lalu `Ctrl+X`.

Apakah ada bagian teknis lain yang ingin Anda tambahkan ke dalam panduan ini?