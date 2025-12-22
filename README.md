✨ Gemini-Metadata: AI-Powered Stock Media Automator
Gemini-Metadata adalah asisten otomasi cerdas yang dirancang khusus untuk kontributor stock media (Photo, Video, & Vector). Alat ini menggabungkan kekuatan Vision AI terkini dengan teknik pemrosesan citra tingkat tinggi untuk menghasilkan metadata yang akurat, relevan, dan siap jual secara otomatis.

🚀 Fitur Utama
Multimodal AI Analysis: Mendukung integrasi dengan Google Gemini, Groq, dan OpenRouter untuk menganalisis konten visual secara mendalam.

Smart Duplication Filter: Menggunakan algoritma dHash (Difference Hashing) dan Color Signature untuk mendeteksi foto burst atau variasi serupa, mencegah pemborosan kuota API.

GPU Accelerated Processing: Deteksi blur dan ketajaman gambar menggunakan FFT (Fast Fourier Transform) yang dipercepat oleh NVIDIA GPU (via CuPy).

Universal Metadata Writing: Penulisan otomatis Title, Description, dan Keywords ke dalam tag EXIF, IPTC, dan XMP menggunakan ExifTool.

WSL-Windows Bridge: Fitur unik yang memungkinkan pengguna WSL (Windows Subsystem for Linux) untuk tetap menggunakan Folder Picker asli Windows melalui PowerShell bridge.

Batch & Live Monitoring: Pilihan untuk memproses ribuan file sekaligus atau memantau folder secara real-time (Live Watchdog).

Agency Ready Reports: Ekspor otomatis ke format CSV yang kompatibel dengan Adobe Stock, Shutterstock, dan Getty Images.

🛠️ Arsitektur Teknologi
Frontend: Streamlit (Dashboard interaktif)

Intelligence: Google Gemini API, OpenAI SDK

Database: SQLite (History & Log Tracking)

Image Core: OpenCV, Pillow, CuPy (GPU)

Metadata Core: PyExifTool (Interface untuk Phil Harvey's ExifTool)

📋 Prasyarat Sistem
Python 3.10+

ExifTool: Harus terinstall di sistem atau diletakkan di folder tools/.

NVIDIA GPU (Opsional): Untuk akselerasi deteksi blur menggunakan library CuPy.

Google Gemini API Key: Diperlukan untuk proses analisis gambar.

⚙️ Instalasi
Clone repositori ini:

Bash

git clone https://github.com/username/gemini-metadata.git
cd gemini-metadata
Jalankan Auto Installer (Khusus Linux/WSL):

Bash

chmod +x setup.sh
./setup.sh
Script ini akan menyiapkan Virtual Environment, menginstall dependensi sistem, dan library Python secara otomatis.

Konfigurasi Environment: Buat file .env di root direktori dan masukkan API Key Anda:

Code snippet

GOOGLE_API_KEY=your_api_key_here
GROQ_API_KEY=your_groq_key_here
🖥️ Cara Penggunaan
Jalankan aplikasi dengan perintah:

Bash

./run.sh
Buka browser di alamat http://localhost:8501.

Metadata Auto: Pilih folder sumber foto Anda. Klik Scan untuk mengecek duplikasi, lalu tekan Start Processing.

Prompt Architect: Gunakan ini jika Anda ingin membuat narasi deskripsi foto yang kreatif sebelum melakukan generatif AI gambar.

History Log: Pantau semua file yang telah diproses dan unduh laporan CSV untuk diunggah ke agensi.

📂 Struktur Proyek
app.py: Antarmuka utama Streamlit.

processor.py: Logika utama alur kerja pemrosesan file.

image_ops.py: Algoritma pemrosesan citra, hashing, dan deteksi blur (GPU/CPU).

ai_engine.py: Driver komunikasi untuk berbagai penyedia AI.

database.py: Manajemen penyimpanan riwayat dan metadata.

utils.py: Fungsi pembantu, termasuk integrasi WSL folder picker.
