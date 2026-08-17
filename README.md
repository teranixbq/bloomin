# 🌸 Sapamin — WhatsApp Bot Toko Bunga

Bot WhatsApp otomatis untuk toko bunga **Sapamin**. Dijalankan dengan **Podman** (rootless), tanpa Docker.

Bot menjawab pertanyaan pelanggan via LLM (DeepSeek) berdasarkan corpus info toko, mengelola sesi chat, dan meneruskan pelanggan ke admin saat diminta.

## Fitur

- 🤖 Jawaban otomatis via **DeepSeek LLM** berdasarkan corpus toko
- 💬 Session chat per pelanggan (history 10 pasang pesan, auto-ping & auto-close)
- 🌸 Terusan ke admin WhatsApp saat pelanggan minta bicara manusia
- 📱 Notifikasi ke owner via WhatsApp & Telegram
- 🖼️ Kirim foto produk ke pelanggan (endpoint `/send/image`)
- ⚙️ Kelola penuh lewat Telegram bot (`/setup`, `/qr`, `/status`, `/systemprompt`, dll)
- 🐳 **Podman native** — hemat ~157MB RAM dibanding Docker (total ±81MB)

## Struktur Project

```
sapamin/
├── podman-compose.yml        # Definisi container (GOWA + Bot)
├── bot/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example          # Template konfigurasi
│   ├── .env                  # Secret (tidak di-commit)
│   ├── config.json           # Config bot — DIHASILKAN via /setup (tidak di-commit)
│   ├── main.py               # FastAPI app
│   ├── core/                 # config, constants, notif
│   ├── services/             # llm, corpus, session
│   └── telegram-bot/         # telegram.py (bot manager Telegram)
├── gowa-data/                # Session WhatsApp (data produksi)
└── docs/
    ├── deployment.md         # Instalasi & deploy di VPS
    ├── running.md            # Operasional harian
    └── setup-telegram.md     # Setup bot Telegram & WhatsApp
```

## Quick Start

```bash
# di VPS
git clone <repo> && cd sapamin
echo '{}' > bot/config.json
cp bot/.env.example bot/.env && nano bot/.env   # isi token Telegram, admin ID, LLM key
podman-compose build
podman-compose up -d
```

Lalu di Telegram:
1. `/start` → `/setup` (brand, corpus, owner)
2. `/qr` → scan QR dengan WhatsApp
3. `/status` → verifikasi koneksi

## Komponen

| Service | Image | Port | Fungsi |
|---|---|---|---|
| `gowa` | `aldinokemal2104/go-whatsapp-web-multidevice:v9.0.1` | 3000 | WhatsApp gateway |
| `bot` | `localhost/sapamin_bot` (build lokal) | 8000 | FastAPI + Telegram bot |

## Dokumentasi

- **[Deployment](docs/deployment.md)** — install Podman di VPS, deploy, update, backup
- **[Running](docs/running.md)** — perintah harian, health check, troubleshooting
- **[Setup Telegram](docs/setup-telegram.md)** — buat bot, setup, QR, verifikasi

## Konfigurasi (`.env`)

| Variable | Wajib | Deskripsi |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token bot dari @BotFather |
| `TELEGRAM_ADMIN_USER_ID` | ✅ | User ID admin (satu-satunya yg boleh akses menu) |
| `GOWA_PUBLIC_URL` | ✅ | `http://IP_VPS:3000` |
| `LLM_API_KEY` | ✅ | API key DeepSeek |
| `GOWA_BASIC_AUTH` | ❌ | Auth GOWA, default `admin:sapamin2024` |
| `GOWA_BASE_URL` | ❌ | `http://gowa:3000` (jangan diubah) |

## Catatan Penting

- **Jangan commit** `bot/.env`, `bot/config.json`, dan `gowa-data/`
- `config.json` dihasilkan otomatis dari `/setup` Telegram — jangan hardcode
- Docker **TIDAK** dipakai — jika ada Docker terpasang, matikan saat Podman jalan agar port tidak konflik (3000/8000)
- Rootless Podman butuh `loginctl enable-linger ubuntu` agar container tetap hidup