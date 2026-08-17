# Setup Telegram Bot & WhatsApp (Panduan Lengkap)

Panduan setup bot **Sapamin** dari awal: buat bot Telegram, konfigurasi via `/setup`, scan QR WhatsApp, dan perintah-perintah yang tersedia.

## Bagian 1 — Buat Bot Telegram

1. Buka Telegram, cari **@BotFather**
2. Ketik `/newbot`
3. Ikuti instruksi untuk memberi nama & username bot
4. BotFather akan mengembalikan **token** dengan format `123456789:ABCdef...`

**Dapatkan User ID kamu (untuk `TELEGRAM_ADMIN_USER_ID`):**
1. Cari **@userinfobot** di Telegram, kirim pesan apa saja
2. Catat `Id` yang ditampilkan (format angka, contoh `1000715121`)

## Bagian 2 — Isi Konfigurasi

Edit `~/sapamin/bot/.env` di VPS:

```bash
nano ~/sapamin/bot/.env
```

Isi minimal yang WAJIB:

```ini
TELEGRAM_BOT_TOKEN=123456789:ABCdef...        # dari BotFather
TELEGRAM_ADMIN_USER_ID=1000715121             # dari @userinfobot
GOWA_PUBLIC_URL=http://YOUR_VPS_IP:3000       # IP publik VPS
GOWA_BASIC_AUTH=admin:sapamin2024
LLM_API_KEY=sk-xxxx                           # API key LLM (DeepSeek)
```

Simpan (`Ctrl+O`, `Enter`, `Ctrl+X`) lalu restart:

```bash
cd ~/sapamin
podman-compose restart bot
```

> **Catatan keamanan**: `TELEGRAM_ADMIN_USER_ID` menentukan siapa yang BISA akses semua perintah admin. Jangan diisi sembarangan.

## Bagian 3 — Setup Bot via Telegram

1. Buka chat dengan bot Sapamin (token baru yang dibuat di Bagian 1)
2. Kirim `/start`
3. Kirim `/setup` — bot akan memandu setup 3 langkah:

| Langkah | Pertanyaan | Contoh Jawaban |
|---|---|---|
| 1/3 | Nama brand toko | `Sapamin` |
| 2/3 | URL corpus (data toko) | `https://drive.google.com/file/d/...` atau URL raw |
| 3/3 | Nomor WhatsApp owner | `6282261144600` |

Setiap langkah bisa di-`Skip` (pertahankan nilai saat ini) atau `Cancel`.

### Format corpus (data toko)

Corpus bisa berupa:
- **Google Drive link** — bot akan mengunduh file, bisa `.txt` atau `.md`
- **URL raw** — file teks yang bisa diakses langsung
- Format isi file: teks biasa berisi info toko (produk, harga, alamat, jam buka, dll)

> Bot memakai **LLM** untuk menjawab. Corpus adalah "sumber kebenaran" — jawaban bot berdasar konten ini. Pastikan lengkap: produk, harga, promo, jam buka, lokasi, cara bayar, pengiriman.

## Bagian 4 — Login WhatsApp via QR

1. Di chat bot Telegram, kirim `/qr`
2. Bot akan mengirimkan **QR code**
3. Buka WhatsApp di HP → **Settings → Linked Devices → Link a Device**
4. Scan QR dengan HP
5. Jika berhasil, bot akan konfirmasi device tersambung

> - QR hanya valid beberapa detik/menit. Jika kedaluwarsa, kirim `/qr` lagi.
> - Sesudah terhubung, **jangan logout HP** dari linked devices — itu akan memutus session.
> - Data session disimpan di `~/sapamin/gowa-data/` — jangan dihapus kecuali mau login ulang.

## Bagian 5 — Verifikasi

### 1. Cek status koneksi WhatsApp

Kirim `/status` di Telegram bot → harus menampilkan koneksi aktif (connected).

### 2. Test chat WhatsApp

Kirim pesan ke nomor yang didaftarkan sebagai owner dari HP lain:

```
Halo, ada rangkaian bunga untuk wisuda?
```

Bot harus membalas dengan jawaban dari corpus (LLM).

### 3. Test lari ke admin

Kirim pesan mengandung kata "admin":

```
Saya mau bicara dengan admin
```

Bot harus menawarkan menghubungkan ke penjual, dan mengirim notifikasi ke nomor owner.

### 4. Test foto

Kirim foto ke bot → bot bisa membalas.

## Bagian 6 — Daftar Perintah Telegram

Perintah admin (hanya untuk `TELEGRAM_ADMIN_USER_ID`):

| Perintah | Fungsi |
|---|---|
| `/start` | Menu utama & status setup |
| `/setup` | Konfigurasi brand, corpus, owner |
| `/qr` | Tampilkan QR code untuk login WhatsApp |
| `/status` | Cek status koneksi WhatsApp |
| `/config` | Lihat konfigurasi saat ini |
| `/welcome` | Edit pesan sambutan bot |
| `/systemprompt` | Edit system prompt LLM |
| `/reload` | Reload corpus dari URL |
| `/restart` | Restart koneksi WhatsApp |
| `/logout` | Logout session WhatsApp |

## Bagian 7 — Mengubah System Prompt (Opsional)

Bot punya default system prompt yang bisa diedit via `/systemprompt`.

Contoh prompt bagus (sudah dipakai untuk Sapamin):

```
Kamu adalah asisten virtual toko bunga {brand_name} yang ramah dan helpful.
Jawab pertanyaan pelanggan berdasarkan informasi toko di bawah ini.

Aturan WAJIB:
- Jawab maksimal 150 kata, padat dan langsung ke inti
- Utamakan informasi dari bagian Informasi Toko
- Boleh improvisasi ringan seputar produk bunga secara umum (misal tips, saran hadiah) TAPI jangan mengarang harga atau nama produk spesifik yang tidak ada di konteks
- Jika pertanyaan sama sekali tidak berkaitan dengan toko atau bunga, balas PERSIS: TIDAK_TAHU
- JANGAN mengarang harga, diskon, atau promo yang tidak tercantum
- JANGAN mulai jawaban dengan salam seperti Halo, Hi, Selamat datang
- Jika pelanggan bingung atau tidak jelas, tanya balik dengan ramah

Format WhatsApp:
- Gunakan *teks* untuk bold
- Gunakan bullet • untuk daftar
- Jangan gunakan # atau **
- Boleh emoji secukupnya

Informasi Toko:
{corpus}
```

**Template**: `{brand_name}` akan diganti nama brand, `{corpus}` akan diganti isi corpus. Jangan hapus kedua placeholder ini.

## Bagian 8 — Troubleshooting Setup

### `/status` mengembalikan error "All connection attempts failed"

GOWA tidak bisa dijangkau bot. Cek:

```bash
podman logs sapamin_gowa_1 | tail -20
curl -u admin:sapamin2024 http://localhost:3000/app/status
```

### QR tidak muncul / expired terus

- Pastikan bot (GOWA) running: `podman ps`
- Ulangi `/qr` — perintah menghasilkan QR baru
- Cek log: `podman logs sapamin_gowa_1`

### Setup `/setup` macet di tengah

Kirim `Cancel`, lalu `/setup` lagi dari awal.

### Bot tidak membalas WhatsApp sama sekali

1. `/status` di Telegram — koneksi aman?
2. `/reload` — corpus termuat?
3. Cek log: `podman logs sapamin_bot_1 | tail -20`
4. Pastikan `is_setup_done: true` di `/config`