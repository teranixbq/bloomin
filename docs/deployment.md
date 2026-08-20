# Deployment ke VPS dengan Podman

Panduan lengkap mendeploy bot WhatsApp **Bloomin** menggunakan **Podman** di VPS.

## Prasyarat

- VPS Ubuntu 24.04 (x86_64 atau ARM64)
- SSH key sudah terdaftar di VPS
- Akun Telegram Bot (dari @BotFather) dengan token
- API key LLM (opsional, default: DeepSeek)
- URL corpus (Google Drive link, direct link, atau URL raw)

## 1. Install Podman & podman-compose di VPS

```bash
sudo apt update
sudo apt install -y podman podman-compose
podman --version
podman-compose --version
```

Konfigurasi registry Docker Hub agar bisa pull image:

```bash
sudo tee /etc/containers/registries.conf > /dev/null << 'EOF'
[registries.search]
registries = ["docker.io"]

[registries.insecure]
registries = []

[registries.block]
registries = []
EOF
```

**PENTING**: Aktifkan systemd user lingering agar container tetap berjalan setelah SSH disconnect:

```bash
loginctl enable-linger ubuntu
```

> Tanpa `enable-linger`, semua container Podman akan mati saat sesi SSH ditutup. Ini akar masalah umum pada Podman rootless.

## 2. Upload Project ke VPS

Dari mesin lokal:

```bash
# Sync seluruh project (kode + docs + compose)
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='bot/config.json' --exclude='bot/.env' --exclude='gowa-data' \
  -e "ssh -i ~/.ssh/vps_not" \
  bloomin/ ubuntu@YOUR_VPS_IP:~/bloomin/

# Atau sync hanya folder bot/ (perhatian: pattern exclude jadi TANPA prefix bot/)
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='config.json' --exclude='.env' \
  -e "ssh -i ~/.ssh/vps_not" \
  bloomin/bot/ ubuntu@YOUR_VPS_IP:~/bloomin/bot/
```

> **⚠️ PENTING — Pattern exclude rsync tergantung source:**
> - Source `bloomin/` → gunakan `--exclude='bot/config.json'`
> - Source `bloomin/bot/` → gunakan `--exclude='config.json'` (tanpa prefix `bot/`)
>
> `config.json`, `bot/.env`, dan `gowa-data/` sengaja di-exclude agar data produksi **tidak tertimpa** saat update.

## 3. Siapkan config.json di VPS

`config.json` dihasilkan otomatis lewat Telegram `/setup`. Untuk instalasi baru, cukup buat file kosong:

```bash
echo '{}' > ~/bloomin/bot/config.json
sudo chown -R ubuntu:ubuntu ~/bloomin
```

## 4. Konfigurasi `.env`

Edit `~/bloomin/bot/.env` di VPS:

```bash
nano ~/bloomin/bot/.env
```

```ini
GOWA_BASE_URL=http://gowa:3000
GOWA_PUBLIC_URL=http://YOUR_VPS_IP:3000
GOWA_BASIC_AUTH=admin:bloomin2024
LLM_API_KEY=sk-xxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=10
LLM_MAX_TOKENS=300
TELEGRAM_BOT_TOKEN=xxxx:xxxxxxxxxxxxxxxxxxx
TELEGRAM_ADMIN_USER_ID=123456789
CONFIG_PATH=./config.json
```

## 5. Build & Jalankan

```bash
cd ~/bloomin
sudo chown -R ubuntu:ubuntu ~/bloomin
podman-compose build
podman-compose up -d
```

Cek status:

```bash
podman ps
curl http://localhost:8000/health
```

Health check yang benar:

```json
{"status":"ok","setup_done":false,"corpus_chars":0,"corpus_url":"","owner_phone":"","active_sessions":0}
```

## 6. Update / Redeploy

Saat ada perubahan kode:

```bash
# dari mesin lokal
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='bot/config.json' --exclude='gowa-data' \
  -e "ssh -i ~/.ssh/vps_not" \
  bloomin/ ubuntu@YOUR_VPS_IP:~/bloomin/

# di VPS
cd ~/bloomin
podman-compose build
podman-compose up -d --force-recreate
```

## 7. Backup & Migrasi

Semua data penting ada di 2 folder:

| Data | Lokasi | Isi |
|---|---|---|
| Session WhatsApp | `~/bloomin/gowa-data/` | device session, DB, media |
| Konfigurasi bot | `~/bloomin/bot/config.json` | corpus, owner, brand, system prompt |

Backup:

```bash
cd ~/bloomin
tar -czf bloomin-backup.tar.gz gowa-data/ bot/config.json
```

Restore di VPS baru:

```bash
cd ~/bloomin
tar -xzf bloomin-backup.tar.gz
sudo chown -R ubuntu:ubuntu ~/bloomin
podman-compose up -d
```

## 8. Troubleshooting

### Container mati setelah SSH disconnect

```bash
loginctl enable-linger ubuntu
podman-compose up -d
```

### GOWA crash: "readonly database"

Permission issue — `gowa-data` dimiliki root. Perbaiki:

```bash
sudo chown -R ubuntu:ubuntu ~/bloomin/gowa-data
podman restart bloomin_gowa_1
```

### GOWA tidak bisa pull image

Pastikan registry Docker Hub sudah dikonfigurasi (lihat langkah 1).

### "short-name did not resolve"

Tulis nama image lengkap dengan prefix `docker.io/` di `podman-compose.yml`.

## 9. Logs

```bash
podman logs -f bloomin_bot_1    # log bot
podman logs -f bloomin_gowa_1   # log GOWA
```

## 10. Hapus / Teardown

```bash
cd ~/bloomin
podman-compose down
podman system prune -a
```
