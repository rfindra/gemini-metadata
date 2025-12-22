# ✨ Gemini-Metadata: AI-Powered Stock Media Automator

**Gemini-Metadata** adalah asisten otomasi cerdas yang dirancang khusus untuk kontributor *stock media* (Photo, Video, & Vector). Alat ini menggabungkan kekuatan **Vision AI** terkini dengan teknik pemrosesan citra tingkat tinggi untuk menghasilkan metadata yang akurat, relevan, dan siap jual secara otomatis.



## 🚀 Fitur Utama

* **Multimodal AI Analysis**: Integrasi dengan Google Gemini (1.5 Flash/Pro, 2.0 Flash) dan penyedia API lainnya untuk analisis visual mendalam.
* **Smart Duplication Filter**: Algoritma **dHash (Difference Hashing)** + **Color Signature** untuk mendeteksi foto *burst* secara presisi, menghemat kuota API hingga 60%.
* **GPU Accelerated Processing**: Deteksi ketajaman (*blur detection*) berbasis **FFT (Fast Fourier Transform)** yang diakselerasi oleh **NVIDIA GPU (via CuPy)**.
* **Universal Metadata Writing**: Penulisan otomatis Title, Description, dan Keywords ke dalam tag **EXIF, IPTC, dan XMP** menggunakan ExifTool.
* **WSL-Windows Bridge**: Solusi unik menggunakan *PowerShell bridge* agar pengguna Linux (WSL) tetap bisa menggunakan *Folder Picker* asli Windows.
* **Isolated Object Detection**: Logika khusus untuk mendeteksi foto dengan latar belakang putih (*isolated*) dan mengategorikannya secara otomatis.



## 🛠️ Arsitektur Teknologi

* **Frontend**: Streamlit (Web-based Dashboard)
* **Intelligence**: Google Gemini API, OpenAI SDK
* **Database**: SQLite (Proses sinkronisasi history & log)
* **Image Core**: OpenCV, Pillow, CuPy (GPU Acceleration)
* **Metadata Core**: PyExifTool (ExifTool Wrapper)

## 📋 Prasyarat Sistem

1.  **Python 3.10+**
2.  **ExifTool**: Terpasang di sistem (PATH) atau di folder `tools/`.
3.  **NVIDIA GPU**: (Opsional) Untuk performa maksimal saat scan ribuan foto.

## ⚙️ Instalasi (Ubuntu 24.04 / WSL)

1.  **Clone Repositori**:
    ```bash
    git clone [https://github.com/username/gemini-metadata.git](https://github.com/username/gemini-metadata.git)
    cd gemini-metadata
    ```

2.  **Jalankan Auto Installer**:
    ```bash
    chmod +x setup.sh
    ./setup.sh
    ```

3.  **Konfigurasi API**:
    Buat file `.env` dan masukkan kunci API Anda:
    ```env
    GOOGLE_API_KEY=your_key_here
    ```

## 🖥️ Cara Penggunaan

1.  Jalankan aplikasi: `./run.sh`
2.  Buka dashboard di browser (`localhost:8501`).
3.  Pilih folder sumber foto menggunakan tombol **Browse**.
4.  Klik **Scan for Duplicates** untuk membersihkan file serupa.
5.  Tekan **Start Processing** dan biarkan AI bekerja untuk Anda.



## 📂 Struktur Proyek

* `app.py`: UI Dashboard & Manajemen State.
* `processor.py`: Logika utama alur pemrosesan file.
* `image_ops.py`: Algoritma hashing, deteksi blur, dan optimasi gambar.
* `ai_engine.py`: Driver untuk berbagai model bahasa (LLM).
* `database.py`: Manajemen penyimpanan riwayat proses.
* `utils.py`: Helper functions & WSL PowerShell Bridge.

---

### 🖋️ Catatan Pengembangan
Alat ini dikembangkan untuk mendemonstrasikan bagaimana AI dapat mengotomatisasi tugas-tugas administratif yang repetitif bagi fotografer profesional, meningkatkan produktivitas tanpa mengorbankan kualitas metadata.

**Author**: Indra (PNS & Tech Enthusiast)
**Status**: Stable (Version 3.1)