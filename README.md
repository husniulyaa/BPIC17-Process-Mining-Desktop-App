# BPIC17 Process Mining Desktop Application

Aplikasi desktop untuk membantu pengguna mengeksplorasi dan menganalisis event log **BPI Challenge 2017 (BPIC17)**. Aplikasi ini dikembangkan menggunakan Python dengan dukungan PM4Py untuk pemrosesan event log serta PySide6 untuk membangun antarmuka desktop.

Melalui aplikasi ini, pengguna dapat memuat dataset berformat XES, melihat gambaran umum data, menjalankan analisis berdasarkan soal latihan, memeriksa urutan aktivitas pada suatu case, dan menyimpan hasil analisis dalam format CSV.

Proyek ini dibuat sebagai bagian dari pembelajaran mata kuliah Data Mining, khususnya untuk memahami bagaimana data event log dapat digunakan dalam analisis proses bisnis (*process mining*).

---

## 1. Fitur Aplikasi

Aplikasi menyediakan beberapa bagian utama yang dapat diakses melalui navigasi pada antarmuka.

### 1.1 Dataset Overview

Halaman ini memberikan gambaran umum mengenai dataset yang sedang dimuat. Informasi yang ditampilkan membantu pengguna memahami karakteristik event log sebelum melakukan analisis lebih lanjut.

### 1.2 Exercise 11.7 (A–E)

Halaman ini menyediakan analisis untuk subsoal A sampai E pada latihan 11.7. Hasil analisis ditampilkan sesuai kriteria masing-masing subsoal, sehingga pengguna dapat memeriksa hasil pencarian case dan informasi pendukungnya.

### 1.3 Exercise 11.15

Halaman ini digunakan untuk mengidentifikasi case yang memiliki setidaknya dua event `W_Assess Potential Fraud` dengan status `complete`.

### 1.4 Exercise 11.18

Halaman ini digunakan untuk mengidentifikasi case yang memiliki setidaknya dua event `W_Assess Potential Fraud` berstatus `complete` yang dilakukan oleh resource yang sama.

### 1.5 Exercise 11.22

Halaman ini digunakan untuk mencari case yang memiliki aktivitas `O_Cancelled` sebelum `O_Accepted` berdasarkan urutan waktu dalam case tersebut.

Halaman ini juga menampilkan ringkasan hasil pencarian, termasuk jumlah case yang memenuhi kriteria dan informasi pendukung lainnya.

### 1.6 Case Explorer

Case Explorer memungkinkan pengguna menelusuri detail suatu case secara lebih spesifik. Pengguna dapat memeriksa rangkaian event yang terjadi dalam case tersebut untuk memahami bagaimana proses berlangsung dari satu aktivitas ke aktivitas berikutnya.

### 1.7 CSV Export

Hasil analisis dapat diekspor ke file CSV agar lebih mudah diperiksa, diolah kembali, atau digunakan sebagai bahan dokumentasi.

---

## 2. Teknologi yang Digunakan

| Teknologi | Kegunaan |
|---|---|
| Python | Bahasa pemrograman utama aplikasi |
| PM4Py | Membaca dan memproses event log serta mendukung analisis process mining |
| Pandas | Mengolah dan menyajikan data dalam bentuk tabular |
| PySide6 | Membangun antarmuka aplikasi desktop |
| Matplotlib | Mendukung kebutuhan visualisasi data |
| Pytest | Menjalankan pengujian otomatis |
| Git & GitHub | Pengelolaan versi dan kolaborasi pengembangan |

Aplikasi dijalankan secara lokal sebagai desktop application. PM4Py digunakan pada bagian pemrosesan dan analisis data, sedangkan PySide6 menangani tampilan serta interaksi pengguna.

---

## 3. Struktur Proyek

Berikut gambaran struktur direktori utama repository:

```text
BPIC17-Process-Mining-Desktop-App/
│
├── main.py
├── preview_app.py
├── requirements.txt
├── requirements-gui.txt
├── README.md
├── TEAM_BASELINE.md
│
├── analysis/
│   ├── exercise_117.py
│   ├── exercise_1115.py
│   ├── exercise_1118.py
│   └── exercise_1122.py
│
├── core/
│   ├── dataset_loader.py
│   └── data_contract.py
│
├── ui/
│   ├── main_window.py
│   └── pages/
│       ├── overview_page.py
│       ├── exercise_117_page.py
│       ├── exercise_1115_page.py
│       ├── exercise_1118_page.py
│       ├── exercise_1122_page.py
│       └── case_explorer_page.py
│
├── utils/
│   ├── case_timeline.py
│   └── exporter.py
│
├── tests/
│   ├── test_dataset_loader.py
│   ├── test_overview_page.py
│   ├── test_exercise_117.py
│   ├── test_exercise_1115.py
│   ├── test_exercise_1118.py
│   ├── test_exercise_1122.py
│   └── test_case_explorer_and_exporter.py
│
├── assets/
│   ├── icons/
│   └── images/
│
└── data/
```

Secara umum, kode dipisahkan berdasarkan tanggung jawabnya:

- `analysis/` berisi logika analisis untuk masing-masing latihan.
- `core/` menangani proses pemuatan dataset dan struktur data yang digunakan bersama.
- `ui/` berisi antarmuka utama dan halaman-halaman aplikasi.
- `utils/` menyediakan fungsi pendukung, seperti penyusunan timeline case dan ekspor data.
- `tests/` berisi pengujian otomatis untuk memeriksa fungsi-fungsi utama aplikasi.
- `assets/` digunakan untuk menyimpan aset visual.
- `data/` disediakan sebagai direktori untuk kebutuhan dataset lokal.

---

## 4. Persyaratan Sistem

Sebelum menjalankan aplikasi, pastikan perangkat telah memiliki:

- Windows, Linux, atau macOS.
- Python yang sudah terpasang.
- Git untuk mengambil repository.
- Koneksi internet saat pertama kali memasang dependency.
- File event log BPIC17 dengan format `.xes`.

Pengembangan dan pengujian proyek menggunakan Python 3.13. Versi Python dan dependency yang digunakan sebaiknya disesuaikan dengan kebutuhan kompatibilitas library.

---

## 5. Instalasi dan Persiapan

Ikuti langkah berikut untuk menyiapkan aplikasi di komputer lokal.

### 5.1 Clone Repository

Buka terminal atau PowerShell, kemudian jalankan:

```powershell
git clone https://github.com/husniulyaa/BPIC17-Process-Mining-Desktop-App.git
cd BPIC17-Process-Mining-Desktop-App
```

Ganti `<URL_REPOSITORY>` dengan alamat repository GitHub proyek.

### 5.2 Membuat Virtual Environment

Virtual environment digunakan agar dependency proyek tidak bercampur dengan instalasi Python lainnya.

```powershell
py -m venv .venv
```

Aktifkan environment:

```powershell
.venv\Scripts\Activate.ps1
```

Jika PowerShell menolak aktivasi karena kebijakan eksekusi script, jalankan perintah berikut pada sesi terminal tersebut:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Kemudian aktifkan kembali:

```powershell
.venv\Scripts\Activate.ps1
```

### 5.3 Memasang Dependency

Pasang seluruh library yang dibutuhkan menggunakan:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Tunggu sampai proses instalasi selesai.

---

## 6. Menjalankan Aplikasi

Setelah instalasi selesai, jalankan aplikasi melalui entry point utama:

```powershell
python main.py
```

Jendela aplikasi akan terbuka dan menampilkan antarmuka utama.

Pastikan virtual environment masih aktif ketika menjalankan aplikasi agar Python menggunakan dependency yang telah dipasang untuk proyek ini.

---

## 7. Panduan Penggunaan

Bagian ini menjelaskan alur penggunaan aplikasi dari awal hingga pengguna memperoleh hasil analisis.

### Langkah 1 — Membuka Aplikasi

Jalankan aplikasi menggunakan perintah `python main.py`.

Setelah jendela utama terbuka, pengguna dapat mengakses halaman-halaman analisis melalui navigasi yang tersedia.

### Langkah 2 — Memuat Dataset BPIC17

Sebelum melakukan analisis, pengguna perlu memuat event log BPIC17 dalam format `.xes`.

Pilih fitur pemuatan dataset pada aplikasi, kemudian arahkan ke lokasi file XES yang ingin digunakan.

Setelah file dipilih, aplikasi akan memproses dataset. Proses pemuatan dilakukan di background agar antarmuka tetap responsif selama data sedang dibaca.

Jika proses berhasil, dataset akan tersedia untuk digunakan pada halaman analisis. Jika terjadi kesalahan, periksa kembali lokasi file, format dataset, dan kelengkapan file yang digunakan.

**Catatan:** Gunakan event log BPIC17 yang sesuai dengan kebutuhan latihan. Pastikan file dapat diakses oleh aplikasi dan tidak sedang dipindahkan atau dihapus ketika proses pemuatan berlangsung.

### Langkah 3 — Melihat Dataset Overview

Setelah dataset berhasil dimuat, buka halaman Dataset Overview.

Halaman ini digunakan untuk melihat ringkasan dataset sebelum melakukan analisis lebih lanjut.

Pengguna dapat memanfaatkan informasi yang ditampilkan untuk memahami ukuran dan karakteristik event log yang sedang digunakan.

### Langkah 4 — Menjalankan Analisis Exercise

Pilih halaman latihan sesuai kebutuhan:

| Halaman | Tujuan Analisis |
|---|---|
| Exercise 11.7 | Menjalankan analisis untuk subsoal A–E |
| Exercise 11.15 | Mencari case dengan minimal dua event `W_Assess Potential Fraud` berstatus `complete` |
| Exercise 11.18 | Mencari case dengan minimal dua event `W_Assess Potential Fraud` berstatus `complete` oleh resource yang sama |
| Exercise 11.22 | Mencari case ketika `O_Cancelled` terjadi sebelum `O_Accepted` |

Hasil analisis dapat diperiksa melalui informasi yang ditampilkan pada masing-masing halaman.

Perlu diperhatikan bahwa setiap latihan memiliki kriteria pencarian yang berbeda. Oleh karena itu, pengguna sebaiknya membaca keterangan pada halaman latihan sebelum menginterpretasikan hasilnya.

### Langkah 5 — Menelusuri Case dengan Case Explorer

Jika ingin memeriksa suatu case lebih detail, buka halaman Case Explorer.

Pilih atau cari case yang ingin diperiksa menggunakan kontrol yang tersedia pada halaman tersebut.

Case Explorer membantu pengguna memahami urutan event yang tercatat pada case, sehingga hasil analisis tidak hanya dilihat sebagai angka atau daftar case, tetapi juga dapat ditelusuri berdasarkan aktivitas yang terjadi.

### Langkah 6 — Mengekspor Hasil Analisis

Untuk menyimpan hasil analisis, gunakan fitur export CSV yang tersedia pada aplikasi.

Pilih hasil atau data yang ingin diekspor sesuai fasilitas pada halaman terkait, kemudian tentukan lokasi penyimpanan file.

File CSV yang dihasilkan dapat dibuka menggunakan Microsoft Excel, LibreOffice Calc, atau aplikasi pengolah data tabular lainnya.

---

## 8. Pengujian

Proyek ini menggunakan Pytest untuk menguji fungsi pemrosesan dataset, logika analisis, halaman overview, serta fitur Case Explorer dan export.

Untuk menjalankan seluruh pengujian, gunakan:

```powershell
python -m pytest -q
```

Untuk menjalankan pengujian pada file tertentu:

```powershell
python -m pytest tests/test_dataset_loader.py -q
```

Hasil pengujian akan menunjukkan jumlah test yang berhasil, gagal, atau dilewati.

Pengujian otomatis membantu memastikan perubahan pada satu bagian aplikasi tidak menyebabkan fungsi lain mengalami regresi.

---

## 9. Penanganan Kendala

Berikut beberapa kendala yang mungkin ditemui ketika menggunakan aplikasi.

| Kendala | Hal yang Perlu Diperiksa |
|---|---|
| `ModuleNotFoundError` | Pastikan virtual environment aktif dan dependency telah dipasang. |
| Aplikasi tidak dapat dibuka | Periksa instalasi Python, PySide6, dan dependency lainnya. |
| Dataset gagal dimuat | Pastikan file memiliki format `.xes`, dapat diakses, dan tidak rusak. |
| Hasil analisis kosong | Periksa apakah dataset yang digunakan memenuhi kriteria latihan. |
| File CSV tidak ditemukan | Periksa kembali direktori penyimpanan yang dipilih ketika melakukan export. |
| Aplikasi terasa belum merespons ketika memuat dataset | Tunggu proses pemuatan selesai dan periksa apakah terdapat pesan kesalahan. |

Jika kendala masih terjadi, periksa pesan error yang muncul pada terminal atau aplikasi untuk membantu menemukan penyebabnya.

---

## 10. Pembagian Tugas Tim

| NIM | Nama | Tanggung Jawab |
|---|---|---|
| 24060124120022 | Nabila Kayla Rafa | Import dataset XES, validasi atribut, konversi DataFrame, dan Dataset Overview |
| 24060124120021 | Husni Ulyaa Khanifah | Kerangka GUI utama, navigasi, shared state/data integration, dan integrasi halaman |
| 24060124120040 | Ovilia Suci Ramadhani | Implementasi Exercise 11.7 A–E |
| 24060124130104 | Mohammad Sulthon Ariefin | Implementasi Exercise 11.15 dan 11.18 |
| 24060124120003 | Farras Hilmy Zaidan | Implementasi Exercise 11.22, Case Explorer, dan CSV Export |

Pembagian tugas tersebut digunakan untuk mengatur proses pengembangan. Setiap bagian kemudian diintegrasikan agar dapat digunakan sebagai satu aplikasi desktop yang saling terhubung.

---

## 11. Kolaborasi dan Pengembangan

Proyek dikembangkan secara kolaboratif menggunakan Git dan GitHub.

Untuk menjaga proses pengembangan tetap teratur, tim menggunakan beberapa aturan berikut:

1. Setiap anggota mengerjakan perubahan melalui branch masing-masing.
2. Perubahan dibuat dalam commit dengan pesan yang menjelaskan pekerjaan yang dilakukan.
3. Branch di-push ke repository remote sebelum proses integrasi.
4. Penggabungan ke branch `main` dilakukan setelah perubahan diperiksa dan diuji.
5. Perubahan pada file bersama perlu dikomunikasikan agar tidak menimbulkan konflik.
6. Virtual environment, file cache, credential, dan dataset berukuran besar tidak dimasukkan ke repository tanpa kesepakatan tim.

---

## 12. Catatan Dataset dan Interpretasi

BPIC17 merupakan event log yang merekam aktivitas dalam proses aplikasi pinjaman. Data tersebut digunakan sebagai bahan analisis untuk memahami urutan aktivitas dan karakteristik proses bisnis.

Hasil analisis sangat bergantung pada atribut dan isi event log yang digunakan. Interpretasi setiap latihan juga perlu mengikuti redaksi soal dan ketentuan yang diberikan dalam materi perkuliahan.

Khusus untuk analisis urutan aktivitas, penting untuk membedakan antara urutan berdasarkan waktu dan aktivitas yang harus terjadi secara berdampingan. Dua aktivitas yang muncul dalam urutan waktu yang benar tidak selalu harus menjadi dua event yang bersebelahan dalam suatu case, kecuali soal memang mensyaratkan demikian.

---

## 13. Penutup

BPIC17 Process Mining Desktop Application dikembangkan untuk menyediakan cara yang lebih terstruktur dalam mempelajari dan menganalisis event log BPIC17.

Dengan menggabungkan pemrosesan data, analisis berdasarkan latihan, penelusuran case, dan ekspor hasil dalam satu aplikasi desktop, proyek ini diharapkan dapat membantu pengguna memahami data event log secara lebih praktis dan sistematis.