# Prompt: Membangun Aplikasi Web "AI Sleep Coach"

Gunakan prompt di bawah ini pada Claude Code, Cursor, v0, atau AI coding assistant lain untuk membangun aplikasi webnya. Sesuaikan bagian **[ISI DI SINI]** sebelum digunakan.

---

## PROMPT

Buatkan aplikasi web full-stack bernama **"AI Sleep Coach"** — aplikasi analisis dan pemantauan kesehatan tidur berbasis Machine Learning. Ikuti spesifikasi berikut secara lengkap.

### 1. Tech Stack
- **Backend:** Python + Flask
- **Database:** SQLite3
- **Machine Learning:** Scikit-Learn (Random Forest Classifier), SHAP (explainability), Joblib (model persistence)
- **AI Generatif:** Google Gemini API (untuk menerjemahkan hasil prediksi + SHAP menjadi penjelasan bahasa alami dan rekomendasi personal)
- **Frontend:** HTML, CSS, JavaScript (vanilla atau ringan — tidak perlu framework berat seperti React)
- **Model ML:** sudah dilatih sebelumnya dan disimpan sebagai `.joblib` (saya akan sediakan file `random_forest_sleep_disorder.joblib` beserta 4 file label encoder: `label_encoder_gender.joblib`, `label_encoder_bmi.joblib`, `label_encoder_occupation.joblib`, `label_encoder_target.joblib`)

### 2. Konteks Aplikasi
Aplikasi ini punya dua komponen utama yang terpisah secara metodologis:

**A. Komponen "Analisis Awal"** (berbasis Machine Learning)
Mendeteksi risiko gangguan tidur pengguna ke dalam 3 kelas: `None` (tidak ada gangguan), `Insomnia`, `Sleep Apnea`.

**B. Komponen "Daily Log"** (berbasis rule-based, BUKAN Machine Learning)
Mencatat kebiasaan tidur harian pengguna dan menghasilkan `Sleep Score` harian menggunakan formula/aturan tetap (bukan model ML), yang ditampilkan lewat fitur "Progress Monitoring".

### 3. Halaman yang Dibutuhkan (sesuai wireframe)
1. **Landing Page** — halaman pengenalan aplikasi (hero section, penjelasan fitur, call-to-action ke Register/Login)
2. **Register & Login** — autentikasi pengguna sederhana (email + password, hash password, session-based auth)
3. **Dashboard** — halaman utama setelah login, menampilkan ringkasan Sleep Score terbaru, akses cepat ke form Daily Log dan Analisis Awal
4. **Halaman Analisis Awal** — form input data pengguna → hasil prediksi risiko → penjelasan SHAP → penjelasan bahasa alami dari Gemini
5. **Halaman Daily Log** — form input kebiasaan tidur harian → hasil Sleep Score hari itu
6. **Halaman Progress Monitoring** — grafik/riwayat Sleep Score dari waktu ke waktu (line chart per hari/minggu)

### 4. Spesifikasi Komponen Analisis Awal (Machine Learning)

**Input form** (field-field berikut, sesuai fitur model):
- Gender (Male/Female)
- Age (numerik)
- Occupation (dropdown, sesuai kategori pekerjaan pada dataset: Accountant, Doctor, Engineer, Lawyer, Manager, Nurse, Sales Representative, Salesperson, dll — [ISI DI SINI: lengkapi dari daftar kategori Occupation di dataset])
- Sleep Duration (jam, desimal)
- Quality of Sleep (skala 1–10)
- Physical Activity Level (menit/hari, numerik)
- Stress Level (skala 1–10)
- BMI Category (Normal/Overweight/Obese)
- Heart Rate (bpm, numerik)
- Daily Steps (numerik)
- Blood Pressure Systolic (numerik)
- Blood Pressure Diastolic (numerik)

**Alur backend saat form disubmit:**
1. Encode field kategorikal (`Gender`, `BMI Category`, `Occupation`) memakai label encoder yang sudah disediakan.
2. Susun fitur sesuai urutan kolom yang dipakai saat training: `['Gender', 'Age', 'Occupation', 'Sleep Duration', 'Quality of Sleep', 'Physical Activity Level', 'Stress Level', 'BMI Category', 'Heart Rate', 'Daily Steps', 'Systolic', 'Diastolic']`
3. Muat model `random_forest_sleep_disorder.joblib`, panggil `.predict()` dan `.predict_proba()`.
4. Hitung nilai SHAP untuk prediksi tersebut memakai `shap.TreeExplainer`.
5. Susun prompt ke Gemini API berisi: hasil prediksi, probabilitas tiap kelas, dan kontribusi SHAP tiap fitur (fitur dengan nilai SHAP absolut terbesar diprioritaskan). Minta Gemini menjawab dalam format: (a) penjelasan singkat kenapa hasilnya seperti itu, dalam bahasa Indonesia awam, dan (b) 3–5 rekomendasi pencegahan yang actionable.
6. Tampilkan ke pengguna: label hasil prediksi, grafik probabilitas per kelas (bar chart sederhana), daftar kontribusi fitur (dari SHAP, divisualisasikan sebagai horizontal bar chart naik/turun), dan teks penjelasan + rekomendasi dari Gemini.

**Catatan penting:** sistem HARUS menampilkan disclaimer yang jelas bahwa hasil ini bukan diagnosis medis dan tidak menggantikan konsultasi dengan tenaga kesehatan profesional.

### 5. Spesifikasi Komponen Daily Log (Rule-Based)

**Input form harian**, 6 variabel (sesuai Bab I & sub-bab 3.7 dokumen):
- Jam mulai tidur (time picker)
- Jam bangun (time picker)
- Tingkat stres (skala 1–10)
- Konsumsi kafein sebelum tidur (jumlah cangkir/porsi, numerik — 0 jika tidak mengonsumsi)
- Durasi olahraga hari itu (menit)
- Durasi penggunaan layar/gadget sebelum tidur (menit)

**Formula Sleep Score** (hitung skor 0–100 per variabel, lalu gabungkan berbobot):

| Variabel | Bobot | Cara Penilaian (Skor 0–100) |
|---|---|---|
| Jam Mulai Tidur | 20% | Skor 100 jika 21:00–23:00; berkurang 10 poin/30 menit penyimpangan dari rentang (minimum 0) |
| Jam Bangun | 15% | Skor 100 jika 05:00–07:00; berkurang 10 poin/30 menit penyimpangan dari rentang (minimum 0) |
| Tingkat Stres | 20% | Skor = (10 − rating) × 10, rating skala 1–10 |
| Konsumsi Kafein Sebelum Tidur | 15% | Skor 100 jika 0 cangkir; berkurang 30 poin per cangkir/porsi (minimum 0) |
| Durasi Olahraga | 15% | Skor 100 jika ≥30 menit/hari; jika <30 menit, Skor = (durasi/30) × 100 |
| Durasi Penggunaan Layar Sebelum Tidur | 15% | Skor 100 jika 0 menit; berkurang 10 poin per 15 menit penggunaan (minimum 0) |

**Rumus akhir:**
```
Sleep Score = (0.20 × Skor Jam Mulai Tidur) + (0.15 × Skor Jam Bangun) + (0.20 × Skor Tingkat Stres)
            + (0.15 × Skor Konsumsi Kafein) + (0.15 × Skor Durasi Olahraga) + (0.15 × Skor Durasi Layar)
```

**Kategori hasil:**
- 80–100 → Baik
- 60–79 → Cukup
- < 60 → Kurang

Simpan setiap entri Daily Log ke tabel database (`user_id`, `tanggal`, nilai tiap variabel, `sleep_score`, `kategori`) agar bisa ditampilkan di halaman Progress Monitoring sebagai riwayat/grafik.

### 6. Struktur Database (SQLite, minimal)
- `users` (id, nama, email, password_hash, created_at)
- `daily_logs` (id, user_id, tanggal, jam_mulai_tidur, jam_bangun, tingkat_stres, konsumsi_kafein, durasi_olahraga, durasi_layar, sleep_score, kategori)
- `analisis_awal` (id, user_id, tanggal, input_data_json, hasil_prediksi, probabilitas_json, shap_values_json, penjelasan_gemini)

### 7. Struktur Folder yang Diharapkan
```
ai-sleep-coach/
├── app.py                      # entry point Flask
├── models/
│   ├── random_forest_sleep_disorder.joblib
│   ├── label_encoder_gender.joblib
│   ├── label_encoder_bmi.joblib
│   ├── label_encoder_occupation.joblib
│   └── label_encoder_target.joblib
├── static/
│   ├── css/
│   └── js/
├── templates/
│   ├── landing.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── analisis_awal.html
│   ├── daily_log.html
│   └── progress_monitoring.html
├── database.db
└── requirements.txt
```

### 8. Desain Visual
- Tema warna: nuansa gelap/malam (biru tua, ungu gelap) dengan aksen lembut, mengesankan ketenangan/tidur — hindari warna-warna terang mencolok.
- Gunakan ikon bertema tidur/malam (bulan, bintang, awan).
- Responsif untuk mobile dan desktop.
- Gunakan card-based layout untuk Dashboard dan hasil Analisis Awal.

### 9. Yang TIDAK perlu dibuat sekarang
- Tidak perlu retraining model (model sudah jadi, tinggal load).
- Tidak perlu autentikasi pihak ketiga (OAuth Google, dll) kecuali diminta.
- Tidak perlu deployment ke cloud — cukup bisa dijalankan lokal dengan `python app.py`.

---

**Sebelum menjalankan prompt ini, siapkan:**
1. File model `.joblib` (5 file) dari notebook yang sudah dibuat.
2. API key Google Gemini (`GEMINI_API_KEY` sebagai environment variable).
