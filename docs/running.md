# Menjalankan Bot Bloomin (Running Guide)

Panduan operasional harian untuk bot WhatsApp **Bloomin** yang berjalan di Podman.

## Perintah Dasar Podman

| Aksi | Perintah |
|---|---|
| Lihat container running | `podman ps` |
| Lihat semua container | `podman ps -a` |
| Log bot real-time | `podman logs -f bloomin_bot_1` |
| Log GOWA real-time | `podman logs -f bloomin_gowa_1` |
| Restart semua | `podman-compose restart` |
| Restart bot saja | `podman restart bloomin_bot_1` |
| Restart GOWA saja | `podman restart bloomin_gowa_1` |
| Start semua | `cd ~/bloomin && podman-compose up -d` |
| Stop semua | `cd ~/bloomin && podman-compose down` |
| Hapus container + network | `cd ~/bloomin && podman-compose down` |

> Semua perintah dijalankan di VPS (`ssh ubuntu@YOUR_VPS_IP`).

## Cek Kesehatan

### Health endpoint bot

```bash
curl http://localhost:8000/health
```

Response yang benar:

```json
{
  "status": "ok",
  "setup_done": true,
  "corpus_chars": 2593,
  "corpus_url": "https://...",
  "owner_phone": "62822xxxxxxx",
  "active_sessions": 0
}
```

| Field | Arti |
|---|---|
| `status: ok` | Bot hidup |
| `setup_done: true` | Setup sudah lengkap |
| `corpus_chars` | Ukuran corpus (0 = belum dimuat) |
| `active_sessions` | Jumlah sesi chat aktif |

### Cek GOWA

```bash
curl -u admin:bloomin2024 http://localhost:3000/app/status
```

## Alur Startup Normal

Saat VPS reboot, container **tidak otomatis start**. Compose memang memakai `restart: unless-stopped`, tapi pada Podman rootless kebijakan restart hanya berlaku saat sistem berjalan (container crash → restart otomatis). Setelah reboot, container baru start lagi jika unit systemd user `podman-restart.service` aktif — di VPS ini statusnya **disabled**. Jalankan manual:

```bash
cd ~/bloomin
podman-compose up -d
```

> **Opsi A** — aktifkan mekanisme bawaan Podman agar restart policy berlaku setelah reboot:
>
> ```bash
> systemctl --user enable --now podman-restart.service
> ```
>
> (butuh `loginctl enable-linger ubuntu` yang sudah dikonfigurasi saat deploy)
>
> **Opsi B** — buat systemd service agar otomatis start saat reboot:
>
> ```bash
> sudo tee /etc/systemd/system/bloomin.service > /dev/null << 'EOF'
> [Unit]
> Description=Bloomin WhatsApp Bot (Podman)
> After=network-online.target
> Wants=network-online.target
>
> [Service]
> User=ubuntu
> WorkingDirectory=/home/ubuntu/bloomin
> ExecStart=/usr/bin/podman-compose up -d
> ExecStop=/usr/bin/podman-compose down
> Restart=on-failure
>
> [Install]
> WantedBy=multi-user.target
> EOF
>
> sudo systemctl daemon-reload
> sudo systemctl enable --now bloomin
> ```

## Sesi Chat WhatsApp (Perilaku Bot)

| Perilaku | Nilai |
|---|---|
| Ping "masih di sini?" | 3 menit tanpa pesan |
| Auto-close sesi setelah ping | 2 menit |
| Sesi owner (admin) | 5 menit |
| History LLM per sesi | 10 pasang pesan (sliding window) |

## Cara Kirim Foto Produk ke Pelanggan

GOWA punya endpoint `/send/image`:

```bash
curl -X POST http://localhost:3000/send/image \
  -u admin:bloomin2024 \
  -H "Content-Type: application/json" \
  -H "X-Device-Id: DEVICE_ID" \
  -d '{
    "phone": "62812xxxxxxx",
    "image_url": "https://link-foto-produk.jpg",
    "caption": "Ini *Bucket Wisuda Rose Gold* 🌹"
  }'
```

**Catatan:**
- URL harus direct link ke file gambar (`.jpg`, `.png`) — bukan Google encrypted thumbnail
- Bisa dari imgbb, Google Drive direct link, atau URL publik lainnya
- `X-Device-Id` diambil dari `~/bloomin/bot/config.json` → field `device_id`

## Troubleshooting Cepat

### Bot tidak merespon Telegram

```bash
podman logs bloomin_bot_1 | grep -iE 'timedout|error|token'
```

### GOWA crash

```bash
podman logs bloomin_gowa_1 | tail -20
# Jika ada "readonly database":
sudo chown -R ubuntu:ubuntu ~/bloomin/gowa-data
podman restart bloomin_gowa_1
```

### Device WhatsApp ke logout / perlu QR ulang

Ketik `/qr` di Telegram bot manager.

## File Penting

| Path (di VPS) | Fungsi |
|---|---|
| `~/bloomin/podman-compose.yml` | Definisi container |
| `~/bloomin/bot/.env` | Konfigurasi secret (token, API key) |
| `~/bloomin/bot/config.json` | Config bot (dihasilkan dari `/setup`) |
| `~/bloomin/gowa-data/` | Session WhatsApp (BACKUP INI!) |
| `~/bloomin/bot/` | Kode aplikasi |
