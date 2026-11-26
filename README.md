# Disco - Lite *(by Kelompok 7)*
**BPIC17 Process Mining Desktop Application**

**Disco - Lite** adalah aplikasi desktop berbasis Python (**PySide6**, **PM4Py**, dan **Pandas**) yang dirancang dengan tampilan dan pengalaman kerja menyerupai **Fluxicon Disco** untuk mengeksplorasi, memvisualisasikan, dan menganalisis data *event log* proses bisnis — khususnya dataset **BPI Challenge 2017 (BPIC17)** (proses pengajuan pinjaman/*loan application*) maupun berbagai file data tabular lainnya.

Aplikasi ini dibuat agar **siapa pun (termasuk pengguna awam)** dapat:
1. Membuka file event log standar (`.xes` / `.xes.gz`) maupun file tabel biasa (`.csv`, `.xlsx`, `.xls`, `.xml`, `.xmx`, `.json`, `.parquet`).
2. Mengatur kolom mana yang berperan sebagai **ID Kasus (*Case ID*)**, **Aktivitas (*Activity*)**, **Waktu (*Timestamp*)**, dan **Petugas (*Resource / Person*)** secara visual.
3. Melihat **Peta Alur Proses (*Process Map*)** otomatis dari awal hingga akhir.
4. Menjalankan berbagai analisis *process mining* (durasi siklus, status tawaran, pemeriksaan *fraud* berulang, hingga tawaran yang dibatalkan lalu diterima kembali).
5. Menelusuri riwayat kejadian (*timeline*) setiap kasus langkah demi langkah dan mengekspor hasilnya ke **CSV** (siap dibuka di Microsoft Excel).

---

## 1. Peta Perubahan Lokasi Fitur & Pembagian Tugas Tim

Pada versi terbaru **Disco - Lite**, penamaan menu tidak lagi menggunakan nomor soal buku teks (`11.7`, `11.15`, `11.18`, `11.22`), melainkan menggunakan **nama fitur *process mining* yang deskriptif**. Seluruh modul perhitungan (`core/` dan `analysis/`) yang dikerjakan masing-masing anggota tim **tetap utuh 100%** dan bekerja di balik layar.

### 1.1 Tabel Pemetaan Fitur Lama ke Lokasi Baru di `Disco - Lite`

| Kode / Fitur Awal | Nama di Versi Lama | Lokasi Sekarang di UI `Disco - Lite` | Apa yang Dilakukan Fitur Ini? | Penanggung Jawab | File Logika Inti (*Backend*) | File Tampilan (*UI*) |
|---|---|---|---|---|---|---|
| **F01** — Import & Validasi XES | Tombol *Import XES* | Tombol **`Open Data…`** (kiri atas) + Pop-up Loading | Membaca file `.xes` / `.xes.gz`, memvalidasi kolom wajib XES, dan menormalkan waktu ke UTC | **Nabila Kayla Rafa** (`24060124120022`) | `core/dataset_loader.py`, `core/data_contract.py` | `ui/main_window.py`, `ui/loading_dialog.py` |
| **F02** — Dataset Overview | Tab `Overview` | Tab **`Statistics`** (beserta sidebar kiri: *Overview*, *Activity*, *Resource*, *Lifecycle transition*) | Menampilkan total event, total kasus, jumlah aktivitas & petugas, rentang waktu, rata-rata/median durasi kasus, grafik distribusi, serta tabel frekuensi | **Nabila Kayla Rafa** (`24060124120022`) | `ui/pages/overview_page.py` (`calculate_case_durations`) | `ui/pages/overview_page.py` |
| **F03** — Exercise 11.7 (A–E) | Tab `Exercise 11.7` + Dropdown `11.7 A–E` | Tab **`Outcomes & Cycle Time`** (pilih subsoal lewat daftar *Outcome cohorts* di panel kiri) | Menghitung total kasus, rata-rata *cycle time*, kasus sukses (`O_Accepted`), ditolak (`O_Refused`), dan berakhir batal (`O_Cancelled`) | **Ovilia Suci Ramadhani** (`24060124120040`) | `analysis/exercise_117.py` | `ui/pages/exercise_117_page.py` |
| **F04** — Exercise 11.15 | Tab `Exercise 11.15` | Tab **`Fraud Rework`** *(Repeated Fraud Assessment)* | Mencari kasus yang mengalami aktivitas `W_Assess Potential Fraud` berstatus `complete` **minimal 2 kali** | **Mohammad Sulthon Ariefin** (`24060124130104`) | `analysis/exercise_1115.py` | `ui/pages/exercise_1115_page.py` |
| **F05** — Exercise 11.18 | Tab `Exercise 11.18` | Tab **`Same-Officer Fraud`** *(Same-Officer Fraud Rework)* | Mencari kasus pada syarat F04 yang dikerjakan minimal 2 kali oleh **petugas (`org:resource`) yang sama** | **Mohammad Sulthon Ariefin** (`24060124130104`) | `analysis/exercise_1118.py` | `ui/pages/exercise_1118_page.py` |
| **F06** — Exercise 11.22 | Tab `Exercise 11.22` | Tab **`Cancelled → Accepted`** *(Re-Accepted Cancelled Offers)* | Mencari kasus yang memiliki event `O_Cancelled` lalu pada waktu lebih akhir memiliki event `O_Accepted` dalam kasus yang sama | **Farras Hilmy Zaidan** (`24060124120003`) | `analysis/exercise_1122.py` | `ui/pages/exercise_1122_page.py` |
| **F07** — Case Explorer & CSV Export | Tab `Case Explorer` | Tab **`Cases`** (kolom *Variants* + *Cases*, mode **`Graph \| Table`**, inspector atribut) & tombol **`Export CSV`** di setiap halaman | Menelusuri urutan aktivitas langkah demi langkah per kasus, mengelompokkan varian alur proses, dan menyimpan tabel/hasil ke CSV | **Farras Hilmy Zaidan** (`24060124120003`) | `utils/case_timeline.py`, `utils/exporter.py` | `ui/pages/case_explorer_page.py` |
| **Integrasi Utama** | *Main Window & Shared State* | Kerangka **`Disco - Lite`** (Header, 8 Tab Navigasi, Footer Aksi, & *Task Load-Balancer*) | Mengelola navigasi antar-halaman, pembagian data bersama (`event_df`), lompatan klik kasus ke tab `Cases`, serta antrean *background thread* agar tidak *freeze* | **Husni Ulyaa Khanifah** (`24060124120021`) & Tim | `main.py`, `ui/task_scheduler.py` | `ui/main_window.py`, `ui/disco_widgets.py` |
| **Ekstensi Baru** — Pemetaan Kolom & Multi-Format | *(Belum ada di versi awal)* | Tab **`Columns`** + Tombol **`Configure Columns`** di footer bawah | Membuka file `.csv`, `.xlsx`, `.xls`, `.xml`, `.xmx`, `.mxml`, `.json`, `.parquet` dan mengatur kolom *Case*, *Activity*, *Timestamp*, *Resource/Person*, *Lifecycle*, atau *Exclude* | Pengembangan Tim (**Kelompok 7**) | `utils/tabular_importer.py` | `ui/pages/column_mapping_page.py` |
| **Ekstensi Baru** — Peta Alur Proses | *(Belum ada di versi awal)* | Tab **`Map`** *(Directly-Follows Process Map)* | Menggambar diagram alur aktivitas otomatis dengan pengaturan slider *Activities %*, *Paths %*, mode *Frequency* / *Performance*, dan *Zoom* | Pengembangan Tim (**Kelompok 7**) | `ui/pages/process_map_page.py` (`compute_process_map_data`) | `ui/pages/process_map_page.py` |

### 1.2 Rincian Lokasi Subsoal Exercise 11.7 (A sampai E)
Untuk memeriksa jawaban subsoal **11.7 A–E** (bagian Ovilia), buka tab **`Outcomes & Cycle Time`**, lalu klik pilihan pada daftar **`Outcome cohorts`** di sebelah kiri:

| Kode Soal Awal | Nama Menu di Sidebar Kiri (`Outcome cohorts`) | Penjelasan Kriteria |
|---|---|---|
| **11.7 A** | **All Active Cases** | Menghitung jumlah seluruh kasus (*case ID* unik) di dalam dataset aktif. |
| **11.7 B** | **Overall Cycle Time** | Menghitung rata-rata durasi siklus (*timestamp* event terakhir dikurangi event pertama, dalam hari) untuk seluruh kasus. |
| **11.7 C** | **Accepted Offers** | Menampilkan kasus unik yang mengandung minimal satu aktivitas `O_Accepted` beserta rata-rata durasinya. |
| **11.7 D** | **Refused Offers** | Menampilkan kasus unik yang mengandung minimal satu aktivitas `O_Refused` beserta rata-rata durasinya. |
| **11.7 E** | **Ended in Cancellation** | Menampilkan kasus unik yang **aktivitas paling terakhirnya** pada urutan waktu adalah `O_Cancelled`. |

---

## 2. Persiapan & Cara Menjalankan Program (Panduan untuk Pemula / Orang Awam)

Anda tidak perlu mengerti pemrograman untuk menjalankan aplikasi ini. Cukup ikuti langkah-langkah berurutan di bawah ini.

### Langkah 1 — Pastikan Python Sudah Terpasang
1. Buka aplikasi **PowerShell** (di Windows: tekan tombol `Windows`, ketik `PowerShell`, lalu tekan `Enter`) atau **Terminal** (di macOS/Linux).
2. Ketik perintah berikut lalu tekan `Enter`:
   ```powershell
   python --version
   ```
3. Jika muncul tulisan seperti `Python 3.11.x`, `Python 3.12.x`, atau `Python 3.13.x`, berarti Python sudah siap.
   - *Jika belum terpasang:* unduh installer gratis dari [https://www.python.org/downloads/](https://www.python.org/downloads/). **PENTING:** Saat menginstal di Windows, wajib centang kotak **"Add python.exe to PATH"** di bagian bawah sebelum klik *Install Now*.

### Langkah 2 — Unduh Kode Aplikasi Ini
Pilih **salah satu** cara berikut:
- **Cara A (Tanpa Git — Paling Mudah untuk Awam):**
  1. Buka halaman GitHub repository ini di browser, klik tombol hijau **`<> Code`**, lalu pilih **`Download ZIP`**.
  2. Ekstrak (*Extract All*) file ZIP tersebut ke folder pilihan Anda (misalnya di `Documents` atau `D:\`).
  3. Buka folder hasil ekstrak tersebut, klik kanan di area kosong, lalu pilih **"Open in Terminal"** (atau buka PowerShell lalu ketik `cd "lokasi\folder\BPIC17-Process-Mining-Desktop-App"`).
- **Cara B (Menggunakan Git):**
  ```powershell
  git clone https://github.com/husniulyaa/BPIC17-Process-Mining-Desktop-App.git
  cd BPIC17-Process-Mining-Desktop-App
  ```

### Langkah 3 — Buat Ruang Kerja Virtual & Pasang Paket Pendukung *(Cukup Sekali Saja)*
Salin dan jalankan perintah berikut satu per satu di jendela PowerShell Anda:

1. Membuat *virtual environment* bernama `.venv` (agar tidak mengganggu program lain di komputer Anda):
   ```powershell
   python -m venv .venv
   ```
   *(Jika perintah `python` tidak dikenali di Windows, ganti menjadi `py -m venv .venv`)*

2. Mengaktifkan `.venv`:
   - **Di Windows (PowerShell):**
     ```powershell
     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
     .venv\Scripts\Activate.ps1
     ```
   - **Di macOS / Linux:**
     ```bash
     source .venv/bin/activate
     ```
   *(Tanda bahwa `.venv` sudah aktif adalah muncul tulisan `(.venv)` berwarna hijau di sebelah kiri baris ketik terminal Anda.)*

3. Memasang seluruh komponen aplikasi (tunggu 1–3 menit hingga selesai; pastikan internet menyala):
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Langkah 4 — Jalankan Aplikasi!

Setiap kali ingin membuka aplikasi, cukup jalankan perintah ini di folder proyek:

- **Opsi 1 — Langsung Coba dengan Data Contoh Bawaan *(Tanpa perlu download dataset besar dulu)*:**
  ```powershell
  .venv\Scripts\python.exe main.py --demo
  ```
  *(Di macOS/Linux: `.venv/bin/python main.py --demo`)*

- **Opsi 2 — Buka Aplikasi Kosong untuk Memuat File Data Sendiri / Dataset BPIC17 Asli:**
  ```powershell
  .venv\Scripts\python.exe main.py
  ```
  *(Di macOS/Linux: `.venv/bin/python main.py`)*

---

## 3. Cara Mendapatkan Dataset Asli BPIC 2017 *(Opsional)*

Jika Anda ingin menguji menggunakan dataset asli **BPI Challenge 2017** (~1,2 juta kejadian, 31.509 pengajuan pinjaman):
1. Buka tautan resmi 4TU.ResearchData: [https://doi.org/10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f](https://doi.org/10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f)
2. Unduh file **`BPI Challenge 2017.xes.gz`** (jika terbungkus `.zip`, ekstrak dulu `.zip`-nya hingga terlihat file `.xes.gz` atau `.xes`).
3. Anda **tidak wajib** mengekstrak `.xes.gz` secara manual — tombol **`Open Data…`** di aplikasi **Disco - Lite** dapat langsung membuka file `.xes.gz` maupun `.xes`!

---

## 4. Panduan Menggunakan Fitur di Dalam Aplikasi

Setelah jendela **Disco - Lite** terbuka:

1. **Membuka Data (`Open Data…` atau `Sample Log` di pojok kiri atas)**
   - Klik **`Sample Log`** bila ingin langsung mencoba seluruh fitur dengan 160 kasus simulasi instan.
   - Klik **`Open Data…`** untuk memilih file Anda sendiri. Format yang didukung:
     - Event log standar: **`.xes`**, **`.xes.gz`**
     - Tabel & spreadsheet: **`.csv`**, **`.tsv`**, **`.txt`**, **`.xlsx`**, **`.xlsm`**, **`.xls`**
     - Dokumen terstruktur: **`.xml`**, **`.xmx`**, **`.mxml`**, **`.json`**, **`.jsonl`**, **`.parquet`**
   - Sebuah **jendela pop-up loading** akan muncul menampilkan tahapan pembacaan dan penghitung waktu berjalan.

2. **Mengatur Peran Kolom di Tab `Columns` *(Khusus CSV/Excel/XML atau jika ingin mengubah atribut)***
   - Bila Anda membuka file tabel (misal `.csv` atau `.xlsx`), aplikasi otomatis membuka tab **`Columns`**.
   - **Klik kolom mana saja** pada tabel (kolom aktif akan disorot **biru tua dengan teks putih**), lalu klik ikon peran di bar biru atas:
     - **Exclude (`✖`)**: Abaikan kolom ini.
     - **Case (`🏷`)**: Gunakan sebagai nomor identitas kasus (*Case ID*) — **wajib tepat 1 kolom**.
     - **Activity (`✉`)**: Gunakan sebagai nama aktivitas/kegiatan — **wajib minimal 1 kolom**.
     - **Timestamp (`🕒`)**: Gunakan sebagai waktu kejadian — **wajib minimal 1 kolom** (bila dipilih **2 kolom**, misalnya *Start Timestamp* & *Complete Timestamp*, aplikasi otomatis menghitung **Service Time / Durasi Pengerjaan** sekaligus **Waiting Time / Waktu Tunggu** serta **Active Time %**!).
     - **Resource (`👥`)**: Gunakan sebagai nama petugas/pelaksana (*Person / Resource*).
     - **Lifecycle (`🔄`)**: Gunakan sebagai status siklus aktivitas (misal `start`, `complete`).
     - **Other (`💬`)**: Simpan sebagai atribut tambahan.
   - **Aturan Kardinalitas Event Log Process Mining yang Ditegakkan Otomatis:**
     1. **Tepat 1 Case ID (*Exactly One Case*):** Setiap kejadian wajib merujuk pada tepat 1 kasus (`Case = 1`). Memilih 0 atau >1 kolom *Case* tidak diizinkan (non-OCPM), dan baris tanpa *Case ID* (*orphan event*) otomatis dibuang agar tidak merusak alur proses.
     2. **Minimal 1 Activity (*At Least One Activity*):** Setiap kejadian dan setiap kasus wajib memiliki minimal 1 aktivitas (`Activity ≥ 1`).
     3. **Minimal 1 Timestamp (*At Least One Timestamp*):** Setiap kejadian wajib memiliki minimal 1 waktu kejadian valid (`Timestamp ≥ 1`) untuk mengurutkan jejak proses secara kronologis, atau 2 waktu (*Start* & *Complete*) untuk memisahkan waktu pengerjaan (*service time*) dari waktu tunggu (*waiting time*).
   - Untuk file CSV, Anda juga dapat menyesuaikan **File encoding**, **Delimiter** (koma, titik koma, tab), **Use quotes**, dan **Timestamp pattern** di bar bawah.
   - Setelah muncul tanda hijau **`✓ Valid`**, klik tombol biru **`Start Import / Apply Mapping ▸`** di kanan bawah.

3. **Menjelajahi Peta Alur Proses di Tab `Map`**
   - Geser slider vertikal **`Activities`** (kanan) untuk menyaring persentase aktivitas yang paling sering muncul.
   - Geser slider vertikal **`Paths`** dari `0%` (hanya jalur utama yang rapi) ke atas untuk memunculkan jalur transisi tambahan.
   - Ganti mode **`Frequency`** (jumlah kejadian/kasus) atau **`Performance`** (rata-rata/total durasi waktu tunggu antar-aktivitas).
   - Gunakan roda *mouse* (*scroll*) atau slider **`Zoom`** di kiri atas untuk memperbesar/memperkecil peta, dan tahan klik kiri untuk menggeser kanvas.

4. **Melihat Ringkasan & Grafik di Tab `Statistics`**
   - Pilih kategori di panel kiri (*Overview*, *Activity*, *Resource*, *Lifecycle transition*) dan pilih jenis grafik di tombol kapsul sebelah kiri grafik hitam (*Events over time*, *Events per case*, *Case duration*, *Activity frequency*).

5. **Memeriksa Hasil Analisis Kasus**
   - Buka tab **`Outcomes & Cycle Time`**, **`Fraud Rework`**, **`Same-Officer Fraud`**, atau **`Cancelled → Accepted`**.
   - Gunakan kotak **`Search case ID...`** untuk mencari nomor kasus tertentu, klik header kolom untuk mengurutkan angka terbesar/terkecil, dan klik **`Open in Cases`** (atau klik dua kali baris kasus) untuk langsung melompat melihat detail alur kasus tersebut.

6. **Menelusuri Detail Kasus di Tab `Cases` & Mengekspor ke CSV**
   - Di tab **`Cases`**, pilih kelompok pola alur pada kolom **`Variants`**, lalu klik nomor kasus pada kolom **`Cases`**.
   - Gunakan tombol **`Graph | Table`** di tengah untuk berpindah antara tampilan **diagram kartu berurutan lengkap dengan selisih waktu** (`Graph`) atau **tabel detail** (`Table`). Klik langkah mana pun untuk membaca seluruh atribut aslinya di kotak bawah.
   - Klik tombol **`Export CSV`** (tersedia di setiap halaman analisis maupun di pojok kanan bawah footer) untuk menyimpan hasil analisis atau riwayat kasus ke file `.csv`.

---

## 5. Struktur Folder Proyek

```text
BPIC17-Process-Mining-Desktop-App/
├── main.py                              # Titik masuk utama untuk menjalankan aplikasi
├── requirements.txt                     # Daftar library Python yang dibutuhkan
├── README.md                            # Dokumentasi & panduan pengguna ini
├── TEAM_BASELINE.md                     # Kesepakatan arsitektur & kontrak data tim
│
├── core/                                # Validasi kontrak XES & pembaca file .xes (PM4Py)
│   ├── data_contract.py
│   └── dataset_loader.py
│
├── analysis/                            # Modul algoritma analisis murni (bebas kode GUI)
│   ├── exercise_117.py                  # Logika Outcomes & Cycle Time (11.7 A–E)
│   ├── exercise_1115.py                 # Logika Repeated Fraud Assessment (11.15)
│   ├── exercise_1118.py                 # Logika Same-Officer Fraud Rework (11.18)
│   └── exercise_1122.py                 # Logika Re-Accepted Cancelled Offers (11.22)
│
├── ui/                                  # Antarmuka desktop PySide6 bergaya Fluxicon Disco
│   ├── main_window.py                   # Jendela utama Disco - Lite (by Kelompok 7)
│   ├── disco_widgets.py                 # Komponen tema, grafik gelap, KPI, & diagram trace
│   ├── loading_dialog.py                # Pop-up modal loading beranimasi
│   ├── task_scheduler.py                # Antrean load-balancer pencegah freeze data besar
│   └── pages/
│       ├── column_mapping_page.py       # Tab Columns (pemetaan kolom interaktif)
│       ├── process_map_page.py          # Tab Map (peta proses hirarki Sugiyama)
│       ├── overview_page.py             # Tab Statistics
│       ├── exercise_117_page.py         # Tab Outcomes & Cycle Time
│       ├── exercise_1115_page.py        # Tab Fraud Rework
│       ├── exercise_1118_page.py        # Tab Same-Officer Fraud
│       ├── exercise_1122_page.py        # Tab Cancelled → Accepted
│       └── case_explorer_page.py        # Tab Cases (Variants + Graph/Table Inspector)
│
├── utils/                               # Utilitas pengolahan timeline, multi-importer, & CSV
│   ├── case_timeline.py
│   ├── exporter.py
│   └── tabular_importer.py
│
├── tests/                               # Rangkaian pengujian otomatis (Pytest / Unittest)
└── data/                                # Folder lokal penyimpanan ekstraksi dataset (gitignored)
```

---

## 6. Menjalankan Pengujian Otomatis *(Untuk Pengembang / Dosen Penguji)*

Untuk memastikan seluruh modul analisis, *importer* multi-format, *exporter* CSV, dan komponen UI berjalan akurat tanpa regresi:

```powershell
.venv\Scripts\python.exe -m pytest -v
```

---

## 7. Solusi Kendala Umum (*Troubleshooting*)

| Kendala yang Muncul | Penyebab & Solusi Mudah |
|---|---|
| Error `running scripts is disabled on this system` saat mengaktifkan `.venv` di PowerShell | Jalankan `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` terlebih dahulu, atau langsung jalankan aplikasi dengan `.venv\Scripts\python.exe main.py` tanpa perlu `Activate.ps1`. |
| Muncul `ModuleNotFoundError: No module named 'PySide6'` (atau `pm4py` / `openpyxl`) | Paket belum terpasang di Python yang sedang dipakai. Jalankan `.venv\Scripts\pip.exe install -r requirements.txt`, lalu buka aplikasi memakai `.venv\Scripts\python.exe main.py`. |
| Tombol **`Start Import / Apply Mapping ▸`** di tab `Columns` masih abu-abu (tidak bisa diklik) | Pastikan minimal sudah ada **1 kolom `Case`**, **1 kolom `Activity`**, dan **1 kolom `Timestamp`** yang dipilih pada bar biru atas (cek keterangan status di sebelah kiri tombol). |
| Isi tabel CSV terlihat menyatu dalam satu kolom | Ubah pilihan **`Delimiter:`** di bagian bawah tab `Columns` (misalnya dari `Comma (,)` ke `Semicolon (;)` atau `Tab`). |
| Memuat file `BPI Challenge 2017.xes` terasa memakan waktu 20–60 detik | Normal untuk pembacaan awal XML berukuran ~550 MB (1,2 juta baris). Tunggu hingga dialog pop-up loading selesai; setelah masuk ke aplikasi, perpindahan tab dan klik kasus sudah dioptimalkan dengan *load-balancer*. |

---

## 8. Anggota Kelompok 7

| NIM | Nama Lengkap | Peran & Kontribusi Utama |
|---|---|---|
| **24060124120022** | **Nabila Kayla Rafa** | Import & validasi file XES, kontrak DataFrame, serta perhitungan *Dataset Overview / Statistics* |
| **24060124120021** | **Husni Ulyaa Khanifah** | Arsitektur jendela utama, navigasi antar-halaman, pengelolaan *shared state*, dan dokumentasi |
| **24060124120040** | **Ovilia Suci Ramadhani** | Implementasi analisis *Case Outcomes & Cycle Time* (Exercise 11.7 A–E) |
| **24060124130104** | **Mohammad Sulthon Ariefin** | Implementasi analisis *Repeated Fraud Assessment* & *Same-Officer Fraud Rework* (Exercise 11.15 & 11.18) |
| **24060124120003** | **Farras Hilmy Zaidan** | Implementasi *Re-Accepted Cancelled Offers* (Exercise 11.22), *Case Explorer*, *CSV Exporter*, desain UI *Disco - Lite*, *Process Map*, & *Multi-Format Column Importer* |
