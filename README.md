# BPIC17 Process Mining Desktop Application

Aplikasi desktop untuk menganalisis event log BPIC17 menggunakan Python dan PM4Py. Aplikasi dirancang agar pengguna dapat memuat file XES, melihat ringkasan dataset, menjalankan analisis sesuai latihan yang ditentukan, menelusuri kasus, dan mengekspor hasil.

> **Status proyek:** tahap persiapan dan pembagian pekerjaan. Fitur yang dijelaskan di bawah merupakan target pengembangan, bukan klaim bahwa seluruh fitur sudah selesai.

## Tujuan

- Memuat dan memvalidasi event log BPIC17 dalam format XES.
- Menampilkan ringkasan dataset dan informasi dasar event log.
- Menyediakan hasil analisis untuk latihan 11.7 (A–E), 11.15, 11.18, dan 11.22.
- Memungkinkan pengguna menelusuri detail kasus beserta urutan event.
- Mengekspor hasil analisis ke CSV.

## Fitur yang direncanakan

| ID | Fitur | Deskripsi |
|---|---|---|
| F01 | Import dan validasi XES | Memuat file XES serta memeriksa atribut yang dibutuhkan. |
| F02 | Dataset overview | Menampilkan ringkasan jumlah case, event, aktivitas, rentang waktu, dan metrik relevan. |
| F03 | Exercise 11.7 A–E | Menampilkan hasil setiap subsoal beserta case ID dan metrik pendukung. |
| F04 | Exercise 11.15 | Menemukan case dengan minimal dua event `W_Assess Potential Fraud` berstatus complete. |
| F05 | Exercise 11.18 | Menemukan case dengan minimal dua event `W_Assess Potential Fraud` berstatus complete oleh resource yang sama. |
| F06 | Exercise 11.22 | Menemukan case ketika `O_Cancelled` terjadi sebelum `O_Accepted` pada case yang sama. |
| F07 | Case Explorer dan export | Menelusuri timeline case dan mengekspor hasil ke CSV. |

Interpretasi akhir setiap latihan harus dicocokkan dengan redaksi instruksi/dokumen dosen. Jangan mengasumsikan event harus berurutan berdampingan jika soal hanya menyebut “followed by” dalam urutan waktu.

## Teknologi

- **Python** sebagai bahasa pemrograman.
- **PM4Py** untuk membaca dan memproses event log serta analisis process mining.
- **Pandas** untuk pengolahan data tabular.
- **PySide6** untuk antarmuka desktop.
- **Matplotlib** bila diperlukan untuk visualisasi.
- **Git dan GitHub** untuk kolaborasi.

PM4Py merupakan library analisis event log, bukan framework antarmuka. PySide6 digunakan untuk membangun GUI desktop. Google Colab boleh digunakan untuk eksperimen analisis secara terpisah, tetapi aplikasi akhir tetap berupa aplikasi desktop yang dijalankan secara lokal.

## Pembagian Tugas Tim

| NIM | Nama Anggota | Tanggung Jawab |
|---|---|---|
| 24060124120022 | Nabila Kayla Rafa | Import dataset XES, validasi atribut, konversi DataFrame, dan Dataset Overview. |
| 24060124120021 | Husni Ulyaa Khanifah | Kerangka GUI utama, navigasi, shared state/data integration, dan integrasi halaman. |
| 24060124120040 | Ovilia Suci Ramadhani | Implementasi Exercise 11.7 A–E. |
| 24060124130104 | Mohammad Sulthon Ariefin | Implementasi Exercise 11.15 dan 11.18. |
| 24060124120003 | Farras Hilmy Zaidan | Implementasi Exercise 11.22, Case Explorer, dan CSV export. |

Setiap anggota bertanggung jawab menguji bagian masing-masing dan mendokumentasikan asumsi atau keterbatasan yang ditemukan.

## Struktur folder yang diusulkan

Struktur berikut adalah target awal dan boleh disesuaikan bersama sebelum implementasi:

```text
BPIC17-Process-Mining-Desktop-App/
├── main.py
├── requirements.txt
├── README.md
├── TEAM_BASELINE.md
├── core/
│   ├── dataset_loader.py
│   └── data_contract.py
├── analysis/
│   ├── exercise_117.py
│   ├── exercise_1115.py
│   ├── exercise_1118.py
│   └── exercise_1122.py
├── ui/
│   ├── main_window.py
│   └── pages/
├── utils/
│   └── exporter.py
└── tests/
```

## Memulai proyek

1. Pastikan Python sudah terpasang.
2. Clone repository.
3. Buat dan aktifkan virtual environment.
4. Pasang dependency setelah `requirements.txt` disepakati dan tersedia.
5. Jalankan aplikasi setelah entry point dan implementasi awal selesai.

Contoh perintah Windows PowerShell:

```powershell
git clone <URL_REPOSITORY>
cd BPIC17-Process-Mining-Desktop-App
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Jangan menganggap aplikasi dapat langsung dijalankan sebelum `main.py` dan dependency tersedia.

## Kolaborasi

- Kerjakan fitur pada branch masing-masing, bukan langsung di `main`.
- Buat commit kecil dengan pesan yang menjelaskan perubahan.
- Push branch dan ajukan Pull Request ke `main`.
- Lakukan review dan pengujian sebelum merge.
- Jangan melakukan force-push ke branch bersama.
- Jangan commit virtual environment, cache, credential, atau dataset berukuran besar tanpa kesepakatan tim.

## Hal yang perlu dikonfirmasi

- Sumber unduhan dan versi file dataset BPIC17 `.xes`.
- Versi Python dan dependency yang akan dipakai bersama.
- Redaksi/interpretasi tepat untuk setiap subsoal berdasarkan instruksi dosen.
- Apakah kelompok beranggotakan lima orang diperbolehkan, karena dokumen instruksi yang dibahas menyebut kelompok beranggotakan empat orang.
