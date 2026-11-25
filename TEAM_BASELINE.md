# TEAM BASELINE — BPIC17 Process Mining Desktop Application

Dokumen ini menjadi acuan kerja bersama agar setiap bagian yang dikembangkan anggota tim dapat diintegrasikan tanpa banyak perubahan ulang. Jika ada perubahan keputusan teknis, diskusikan terlebih dahulu dan perbarui dokumen ini.

## 1. Ruang lingkup

Target fitur:

- **F01:** import dan validasi file XES.
- **F02:** dataset overview.
- **F03:** Exercise 11.7 A–E.
- **F04:** Exercise 11.15.
- **F05:** Exercise 11.18.
- **F06:** Exercise 11.22.
- **F07:** Case Explorer, evidence/timeline, dan CSV export.

## 2. Pembagian tanggung jawab

| Anggota | File/area utama | Tanggung jawab |
|---|---|---|
| Nab | `core/` dan halaman overview | Loader XES, validasi, DataFrame, statistik dataset. |
| Husni | `main.py`, `ui/main_window.py`, integrasi UI | Main window, navigasi, shared state, integrasi halaman. |
| Ovi | `analysis/exercise_117.py`, halaman 11.7 | Analisis subsoal A–E. |
| Sulthon | `analysis/exercise_1115.py`, `analysis/exercise_1118.py` | Analisis 11.15 dan 11.18. |
| Farras | `analysis/exercise_1122.py`, Case Explorer, exporter | Analisis 11.22, detail case, ekspor CSV. |

File tambahan boleh dibuat jika memang diperlukan, tetapi koordinasikan lebih dulu agar tidak terjadi konflik perubahan.

## 3. Kontrak data bersama

Data event yang dibagikan antar-modul menggunakan Pandas DataFrame dengan nama atribut event log yang dipertahankan.

Atribut inti:

- `case:concept:name` — ID case.
- `concept:name` — nama aktivitas.
- `time:timestamp` — timestamp event.

Atribut yang dibutuhkan untuk analisis tertentu:

- `lifecycle:transition` — status lifecycle, misalnya `complete`.
- `org:resource` — resource yang mengerjakan event.

Loader harus memeriksa atribut inti dan memberi pesan error yang jelas jika atribut wajib tidak tersedia. Atribut lifecycle dan resource harus diperiksa sebelum analisis yang membutuhkannya dijalankan. Jangan diam-diam menganggap kolom yang hilang sebagai nilai tertentu.

Jangan mengganti nama kolom standar secara sepihak. Jika perlu normalisasi, lakukan di loader dan dokumentasikan hasilnya.

## 4. Konvensi fungsi analisis

Gunakan fungsi publik dengan pola yang konsisten, misalnya:

```python
def analyze_exercise(event_df):
    # proses analisis
    return {
        "exercise": "11.x",
        "rule": "Deskripsi aturan yang diterapkan",
        "total_cases": 0,
        "case_ids": [],
        "details": []
    }
```

Ketentuan:

- Fungsi menerima DataFrame event sebagai input.
- Fungsi tidak membaca file dataset sendiri.
- Fungsi tidak bergantung pada variabel global.
- Fungsi mengembalikan hasil terstruktur, bukan hanya mencetak output.
- GUI bertugas menampilkan hasil, bukan mengulang logika analisis.
- Sertakan detail/evidence yang cukup agar hasil dapat diperiksa.
- Jangan hard-code jumlah case, ID case, atau hasil analisis.

Nama key tambahan boleh disesuaikan dengan kebutuhan subsoal, tetapi bentuk hasil utama harus disepakati bersama.

## 5. Aturan interpretasi latihan

### Exercise 11.7 A–E

- Hitung jumlah case secara unik, bukan jumlah baris event.
- Average cycle time dihitung per case dari timestamp event terakhir dikurangi timestamp event pertama, kemudian dirata-ratakan sesuai definisi soal.
- Untuk pencarian case berdasarkan aktivitas, gunakan ID case unik.
- Untuk subsoal yang meminta aktivitas terakhir `O_Cancelled`, urutkan event berdasarkan timestamp di dalam masing-masing case dan periksa event terakhir.
- Tampilkan case ID dan metrik yang mendukung hasil.
- Pastikan definisi cycle time dan satuan hasil mengikuti instruksi dosen.

### Exercise 11.15

Identifikasi case yang memiliki setidaknya dua event `W_Assess Potential Fraud` dengan `lifecycle:transition` bernilai `complete`.

Hitung occurrence berdasarkan event yang memenuhi kedua kondisi tersebut. Jangan menghitung event dengan lifecycle lain.

### Exercise 11.18

Terapkan kondisi Exercise 11.15, lalu periksa apakah setidaknya satu resource yang sama melakukan minimal dua occurrence yang memenuhi syarat dalam case yang sama.

Gunakan `org:resource` untuk identitas resource. Tangani nilai resource kosong secara eksplisit; jangan menganggap dua nilai kosong sebagai resource yang sama.

### Exercise 11.22

Identifikasi case yang memiliki event `O_Cancelled` dan kemudian, pada waktu yang lebih akhir, memiliki event `O_Accepted` dalam case yang sama.

- Urutkan event berdasarkan timestamp dalam case.
- `O_Accepted` harus terjadi setelah `O_Cancelled`.
- Keduanya tidak harus bersebelahan kecuali redaksi soal menyatakan demikian.
- Tampilkan case ID dan timeline/evidence yang relevan.

Jika timestamp sama, jangan membuat asumsi urutan yang tidak didukung data; dokumentasikan penanganannya.

## 6. Konvensi GUI

- Gunakan satu `QApplication` dan satu main window.
- Halaman fitur dibuat sebagai `QWidget` atau komponen turunan yang sesuai.
- Halaman tidak membuat `QApplication` atau event loop sendiri.
- Main window menjadi pengelola navigasi dan data event bersama.
- Setiap halaman menerima data melalui metode yang konsisten, misalnya `set_event_data(event_df)`.
- Tampilkan loading state saat proses yang membutuhkan waktu berjalan.
- Tampilkan pesan error yang bisa dipahami pengguna; jangan hanya mencetak traceback.
- Hindari menjalankan analisis berat di UI thread jika membuat aplikasi tidak responsif.

## 7. Git dan GitHub workflow

Nama branch yang diusulkan:

- `feature/dataset-overview`
- `feature/main-gui`
- `feature/exercise-117`
- `feature/exercise-1115-1118`
- `feature/exercise-1122-explorer`

Alur kerja:

1. Sinkronkan `main` sebelum mulai.
2. Buat atau pindah ke branch fitur sendiri.
3. Kerjakan hanya area yang menjadi tanggung jawab, kecuali perubahan lintas-modul sudah dikoordinasikan.
4. Jalankan pemeriksaan/test lokal.
5. Commit dengan pesan yang jelas.
6. Push branch dan buat Pull Request.
7. Minta anggota lain melakukan review.
8. Merge setelah konflik dan test diselesaikan.

Jangan mengerjakan langsung di `main`, jangan force-push ke branch bersama, dan jangan menghapus perubahan anggota lain. Hindari commit `.venv/`, cache, file rahasia, dan dataset besar.

## 8. Strategi kerja paralel

- Anggota analisis dapat mulai dengan DataFrame sintetis sambil menunggu loader dataset selesai.
- Pengembang GUI dapat membuat halaman placeholder dengan data contoh yang diberi label sebagai dummy.
- Setelah loader siap, uji seluruh modul dengan DataFrame hasil loader.
- Integrasikan satu fitur pada satu waktu melalui Pull Request.
- Jangan mengubah kontrak data atau signature fungsi bersama tanpa memberi tahu anggota lain.

## 9. Pengujian minimum

Uji setidaknya:

- File XES valid dan file yang tidak dapat dibaca.
- Atribut inti hilang.
- Atribut lifecycle/resource hilang saat fitur terkait dipanggil.
- Case dengan satu event dan beberapa event.
- Timestamp terurut dan tidak terurut.
- Case tanpa aktivitas target.
- Case dengan event target berulang.
- Resource berbeda, sama, atau kosong.
- `O_Cancelled` tanpa `O_Accepted`.
- `O_Accepted` sebelum `O_Cancelled`.
- `O_Accepted` setelah `O_Cancelled` dengan event lain di antaranya.
- Dataset kosong atau hasil analisis kosong.

Pastikan hasil analisis dapat ditelusuri kembali ke event sumber. Gunakan fixture kecil agar hasil yang diharapkan bisa dihitung manual.

## 10. Hal yang belum diputuskan

Catat dan sepakati bersama sebelum finalisasi:

- Sumber resmi dan versi dataset BPIC17 XES.
- Versi Python dan versi paket yang kompatibel.
- Redaksi lengkap setiap subsoal dari instruksi dosen.
- Format tampilan dan desain GUI.
- Kebijakan penyimpanan dataset dan hasil ekspor.
- Ketentuan jumlah anggota kelompok: instruksi yang dibahas menyebut empat orang, sedangkan tim saat ini terdiri dari lima orang. Konfirmasikan kepada dosen.

## 11. Prinsip umum

- Utamakan kode yang sederhana, terbaca, dan mudah diintegrasikan.
- Jangan mengasumsikan data selalu lengkap atau terurut.
- Pisahkan logika analisis, pengelolaan data, dan tampilan GUI.
- Jangan menyatakan fitur selesai sebelum diuji.
- Jika menemukan ambiguitas pada soal atau dataset, dokumentasikan dan diskusikan; jangan menutupinya dengan asumsi diam-diam.
