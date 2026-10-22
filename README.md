# Panduan Sistem Text-to-SQL

Dokumen ini menjelaskan arsitektur aplikasi SouthCity Text-to-SQL dan cara
menjalankannya secara lokal. Aplikasi menggunakan FastAPI, LangChain, model
chat yang dapat dipilih melalui konfigurasi, dan Microsoft SQL Server.

## Arsitektur dan alur Text-to-SQL

```text
Klien
  │ POST /ask { "prompt": "..." } + header user_role
  ▼
FastAPI (app/routes.py)
  ├─ Pemeriksaan prompt injection (app/security.py)
  ├─ Pembuatan satu query T-SQL (app/text_to_sql.py)
  │    └─ Schema untuk Sales_Staff tidak menyertakan GL_Journals
  ├─ Validasi query dan batasan akses role
  ├─ Eksekusi read-only ke SQL Server (app/database.py)
  └─ Perangkuman hasil dalam bahasa Indonesia
       ▼
    Jawaban JSON
```

Urutan pemrosesan permintaan:

1. `POST /ask` menerima pertanyaan pada properti `prompt` dan header wajib
   `user_role`. Role yang didukung adalah `Sales_Staff` dan `Management`.
2. Sebelum pertanyaan diteruskan ke generator, model memeriksa apakah input
   merupakan prompt injection. Label selain `SAFE` atau `INJECTION`, atau
   kegagalan pemeriksaan, menghentikan permintaan.
3. Model Text-to-SQL menerima instruksi T-SQL dan schema ERP. Untuk
   `Sales_Staff`, schema `GL_Journals` dihilangkan; `Management` mendapat
   schema lengkap. Model diminta menghasilkan satu query `SELECT`.
4. Server memvalidasi hasil: harus tepat satu statement `SELECT`, tanpa
   komentar SQL atau operasi yang dilarang. Akses `Sales_Staff` ke
   `GL_Journals` juga ditolak. Hasil query dibatasi maksimal 200 baris di
   aplikasi (prompt generator meminta maksimal 100 baris untuk query detail).
5. Query dijalankan pada SQL Server, kemudian model merangkum hasil yang
   dikembalikan dalam bahasa Indonesia. Ringkasan diarahkan agar tetap
   berdasarkan hasil database dan memformat nilai uang sebagai Rupiah.
6. API mengembalikan jawaban dengan bentuk `{"answer": "..."}`. Kegagalan
   guardrail atau koneksi dikembalikan sebagai error API dan tidak dianggap
   sebagai jawaban berhasil.

Endpoint pendukung:

- `GET /db/health` memeriksa koneksi SQL Server.
- `GET /docs` menyediakan dokumentasi interaktif FastAPI.


## Demo video

- Demo aplikasi: https://drive.google.com/file/d/1Y1RD5SNm08geNLYbVgFOKUGGlv_wSkd4/view?usp=sharing

## Menjalankan aplikasi secara lokal (Windows PowerShell)

### Prasyarat

- Python yang didukung oleh dependency proyek.
- Microsoft SQL Server yang dapat diakses dari komputer lokal.
- Microsoft ODBC Driver 18 for SQL Server. Aplikasi menggunakan driver ini
  secara default.
- API key untuk salah satu provider LLM yang didukung.

### 1. Buat virtual environment dan pasang dependency

Jalankan perintah dari direktori root repository:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Jika PowerShell memblokir aktivasi virtual environment, gunakan executable
Python environment secara langsung, misalnya
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

### 2. Siapkan SQL Server dan database

1. Buat database SQL Server untuk aplikasi dan pastikan akun Windows yang
   menjalankan aplikasi memiliki akses ke database tersebut.
2. Jalankan [schema.sql](./schema.sql) sekali terhadap database tersebut
   menggunakan SQL Server Management Studio atau alat SQL Server lain. File
   ini membuat tabel ERP sekaligus memasukkan data dummy untuk pengujian;
   menjalankannya ulang pada database yang sama akan menemui tabel/data yang
   sudah ada.
3. Pastikan ODBC Driver 18 for SQL Server telah terpasang.

Koneksi aplikasi menggunakan Windows Integrated Authentication
(`Trusted_Connection=yes`), enkripsi koneksi, dan `TrustServerCertificate=yes`.
Untuk autentikasi SQL Server atau pengaturan TLS yang berbeda, ubah konfigurasi
koneksi di `app/database.py` sesuai kebijakan lingkungan Anda.

### 3. Konfigurasikan environment

Salin template ke `.env` di root repository. File `.env` diabaikan Git agar
nilai lokal, terutama API key, tidak ikut di-commit:

```powershell
Copy-Item .env_template .env
```

Edit `.env`, isi `LLM_PROVIDER`, `LLM_MODEL`, `GROQ_API_KEY`, serta nama server
dan database SQL Server. `.env_template` menyediakan variabel Groq sebagai
contoh awal:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
GROQ_API_KEY=isi-api-key-groq
SQL_SERVER_DRIVER=ODBC Driver 18 for SQL Server
SQL_SERVER_NAME=localhost
SQL_SERVER_DATABASE=NamaDatabaseAnda
SQL_GENERATION_TEMPERATURE=0.0
RESPONSE_SYNTHESIS_TEMPERATURE=0.3
```

Ganti nama server dan database dengan nilai yang benar; contoh `localhost`
hanya cocok jika SQL Server lokal tersedia di sana. `LLM_PROVIDER`,
`LLM_MODEL`, kedua temperature, dan API key provider yang dipilih harus
dikonfigurasi. `SQL_SERVER_NAME` dan `SQL_SERVER_DATABASE` juga wajib.
`SQL_SERVER_DRIVER` opsional karena memiliki default ODBC Driver 18. Jangan
masukkan API key ke Git atau membagikannya.

### 4. Memilih provider LLM selain Groq

Integrasi LangChain untuk Groq, OpenAI, dan Anthropic sudah tercantum di
`requirements.txt`. Tidak perlu mengubah kode aplikasi untuk berpindah di
antara provider tersebut. Saat memilih provider selain Groq, ubah nilai
`LLM_PROVIDER` dan `LLM_MODEL` di `.env`, lalu tambahkan API key provider
tersebut. Template hanya menyediakan baris `GROQ_API_KEY`, jadi tambahkan
variabel untuk provider lain secara manual:

**OpenAI**

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=isi-api-key-openai
```

**Anthropic**

```dotenv
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-latest
ANTHROPIC_API_KEY=isi-api-key-anthropic
```

Untuk kembali menggunakan Groq:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
GROQ_API_KEY=isi-api-key-groq
```

Gunakan nama provider dan ID model yang tersedia untuk akun/provider Anda.
Pastikan API key provider yang dipilih valid; aplikasi tidak otomatis
berpindah provider jika konfigurasi atau pemanggilan model gagal.

### 5. Jalankan dan uji

```powershell
python -m uvicorn main:app --reload
```

Secara default, API tersedia di `http://127.0.0.1:8000`. Buka
`http://127.0.0.1:8000/docs` untuk mencoba endpoint, atau periksa koneksi
database melalui `GET http://127.0.0.1:8000/db/health`.

Contoh request PowerShell:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/ask `
  -Method Post `
  -Headers @{ user_role = "Management" } `
  -ContentType "application/json" `
  -Body (@{ prompt = "Berapa total nilai kontrak sales atas nama Budi Santoso?" } | ConvertTo-Json)
```

Ganti `Management` dengan `Sales_Staff` untuk menguji akses role staf sales.
Untuk menjalankan smoke test API terhadap skenario yang tersedia, pastikan
server berjalan lalu gunakan:

```powershell
python scripts\smoke_test.py
```

Smoke test mengirim skenario API ke server yang sedang berjalan. Jalankan
server di terminal lain terlebih dahulu. Untuk mengubah URL API atau waktu
tunggu, gunakan `python scripts\smoke_test.py --base-url http://localhost:8000 --timeout 180`.

Log aplikasi ditampilkan di konsol dan disimpan di `logs/` dalam file harian.
Output SQL hasil generasi dan jawaban model dicatat; prompt pengguna dan hasil
database tidak dicatat.
