# Bloomin' AI Bot - Dokumentasi Bisnis

Bot WhatsApp AI untuk customer service toko bunga (atau bisnis lainnya) dengan integrasi LLM, Telegram admin panel, dan sistem session management yang canggih.

## 📋 Overview

**Nama Project:** Bloomin' AI Bot  
**Platform:** WhatsApp (via GOWA) + Telegram (Admin Panel)  
**Backend:** FastAPI + Python  
**AI Engine:** LLM (DeepSeek/OpenAI-compatible API)  
**Deployment:** Podman/Docker Compose

## 🎯 Tujuan Bisnis

1. **Automasi Customer Service 24/7** - Bot menjawab pertanyaan umum tentang produk/jam operasional
2. **Efisiensi Admin** - Admin hanya dihubungi untuk kasus khusus (media, spam, pertanyaan kompleks)
3. **Multi-Channel** - User via WhatsApp, Admin kontrol via Telegram
4. **Smart Session Management** - Otomatis handle timeout, spam, outside hours tanpa intervensi manual

## 🏗️ Arsitektur Sistem

```
┌─────────────────┐
│  User WhatsApp  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   GOWA Gateway  │ ← WhatsApp Web Bridge
│  (Port 3000)    │
└────────┬────────┘
         │ Webhook
         ▼
┌─────────────────┐
│  FastAPI Bot    │ ← Main Application
│  (Port 8000)    │
│                 │
│  - Session Mgmt │
│  - Spam Filter  │
│  - Media Handle │
│  - LLM Router   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────┐
│   LLM  │ │ Telegram │
│  API   │ │  Admin   │
└────────┘ └──────────┘
```

## 📁 Struktur File

```
/root/bloomin/
├── bot/
│   ├── main.py                 # Entry point + webhook handler
│   ├── services/
│   │   ├── session.py          # Session & timer management
│   │   ├── llm.py              # LLM integration
│   │   └── notif.py            # WhatsApp notification helpers
│   ├── core/
│   │   ├── constants.py        # Pesan, keywords, timeout values
│   │   └── config.py           # Config loader
│   └── telegram-bot/
│       └── telegram.py         # Telegram admin commands
├── docs/                       # Dokumentasi ini
├── podman-compose.yml
└── bot/.env                    # Environment variables
```

## 🔑 Fitur Utama

### 1. Smart Message Routing
- **Normal Chat** → LLM AI Response
- **Media (gambar/video/dll)** → Auto-forward ke admin
- **Spam (5+ pesan dalam 10 detik)** → Auto-forward ke admin
- **Outside Hours** → Kirim info jam operasional, skip session
- **Keyword /admin** → Konfirmasi lalu forward ke admin

### 2. Session Management
- **Normal Session**: 5 menit inactivity → ping → 2 menit lagi → auto-close
- **Owner Session**: 5 menit tanpa respon admin → timeout + notifikasi
- **Outside Hours**: 1x reminder, skip nomor via set (no session overhead)

### 3. Admin Integration
- **Telegram Commands**: /qr, /setup, /knowledge, /worktime, /admin, dll
- **WhatsApp Notification**: Admin dapat notif saat user butuh bantuan
- **Real-time Control**: Admin bisa balas langsung dari WhatsApp

### 4. Knowledge Base
- **File-based**: `/app/knowledge.txt` (editable via Telegram)
- **LLM Context**: Knowledge di-inject ke system prompt
- **Hot Reload**: Upload file baru → auto-reload tanpa restart

## 📊 Dokumentasi Lengkap

- [Architecture & Flow](architecture.md) - Diagram alur pesan & state machine
- [Scenarios](scenarios.md) - Contoh skenario dengan step-by-step
- [Session Management](session-management.md) - Detail timer & state transitions
- [API Reference](api-reference.md) - Webhook payload & response format

## 🚀 Quick Start

```bash
# 1. Clone & setup
cd /root/bloomin
cp bot/.env.example bot/.env
# Edit .env dengan credentials

# 2. Build & run
podman-compose up -d

# 3. Scan QR via Telegram
# Kirim /qr ke bot Telegram

# 4. Setup knowledge
# Kirim /setup di Telegram, ikuti wizard
```

## 📝 Changelog

### v2.0 (2024) - Current Version
- ✅ Media auto-forward (deteksi dari payload keys)
- ✅ Spam detection (5+ messages in 10s)
- ✅ Outside hours skip (set tracking)
- ✅ Owner session logic fix (proper timer switching)
- ✅ Knowledge base via file (not JSON)
- ✅ Closing keyword ignore saat owner connected

### v1.0 (Initial)
- Basic LLM chat
- Telegram admin panel
- Session timeout

---

**Maintained by:** Hanief  
**Last Updated:** 2024
