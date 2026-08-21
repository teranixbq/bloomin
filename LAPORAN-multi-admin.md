# Laporan Perubahan: Multi-Admin Telegram

**Tanggal:** 2026-08-21 (WIB)
**Status:** ✅ Selesai & terverifikasi

## Ringkasan

Bot Bloomin sekarang mendukung **lebih dari satu admin Telegram** lewat satu variabel env, dipisah koma. Sebelumnya hanya satu ID yang didukung (hardcast `int`).

## Nilai env baru

```
TELEGRAM_ADMIN_USER_ID=1000715121,8209280055,7157785504
```

Separator: **koma** (spasi setelah koma juga boleh, di-trim otomatis). Format lama satu ID tetap kompatibel.

## File yang diubah (3 titik)

### 1. `bot/telegram-bot/telegram.py`
- **Baris 16-21:** parsing env jadi set of int:
  ```python
  TELEGRAM_ADMIN_IDS = {
      int(x.strip())
      for x in os.getenv("TELEGRAM_ADMIN_USER_ID", "0").split(",")
      if x.strip()
  }
  ```
- **Fungsi `is_admin()`:** sekarang cek keanggotaan:
  ```python
  return update.effective_user.id in TELEGRAM_ADMIN_IDS
  ```
  Semua command admin (`/setup`, `/config`, `/qr`, `/status`, `/logout`, `/restart`, `/reload`, `/welcome`, `/systemprompt`, dll.) otomatis ikut mendukung multi-admin karena semua lewat `is_admin()`.

### 2. `bot/main.py`
- Notifikasi "Bot baru saja restart dan konfigurasi tidak ditemukan" sekarang dikirim **ke semua admin ID** (loop), bukan cuma satu. Gagal kirim ke satu ID tidak menghentikan pengiriman ke ID lain.

### 3. `bot/.env`
- `TELEGRAM_ADMIN_USER_ID` diupdate ke `1000715121,8209280055` (menggantikan `1000715121`).
- Permission tetap 600.

## Deploy

- Image `bloomin_bot` di-**rebuild** (kode di-build ke image, bukan di-mount volume).
- Container `bloomin_bot_1` di-force-recreate dengan env baru.
- Container `gowa` tidak disentuh.

## Verifikasi (sudah dilakukan)

| Cek | Hasil |
|---|---|
| `GET /health` | ✅ `{"status":"ok","setup_done":true,...}` |
| Log startup | ✅ Application startup complete, corpus 1762 char termuat |
| Parsing env di dalam container | ✅ `ADMIN_IDS parsed: [1000715121, 8209280055]` |

## Catatan

- Setelah perubahan admin, **tes manual**: minta kedua akun (`1000715121` dan `8209280055`) kirim `/status` ke bot — dua-duanya harus direspon.
- Riwayat: awalnya tertulis `1000715122` (typo 1 digit), sudah dikoreksi ke `1000715121` tanpa rebuild (env di-pass via `--env-file`, cukup recreate container).
- Dokumentasi repo (`README.md`, `docs/setup-telegram.md`, `docs/deployment.md`) masih menyebut format satu ID — sudah dicatat untuk diupdate.

---

# Laporan Perubahan 2: LLM_MAX_TOKENS 300 → 800

**Tanggal:** 2026-08-21 (WIB)
**Status:** ✅ Selesai & terverifikasi

## Masalah
Balasan AI bot ke pelanggan **terpotong** saat customer minta katalog lengkap — pesan putus di `• 15 lembar: Rp` tanpa harga. Penyebab: `LLM_MAX_TOKENS=*** (default env) terlalu kecil untuk katalog 20+ item (~500-700 token output). Log menunjukkan total token request 1250-1588 dengan output mentok di 300.

## Perubahan
- `bot/.env`: `LLM_MAX_TOKENS` **300 → 800**
- Rebuild image `bloomin_bot` + force-recreate container
- Tidak ada perubahan kode

## Verifikasi
| Cek | Hasil |
|---|---|
| `GET /health` | ✅ `{"status":"ok","setup_done":true,...}` |
| Env di container | ✅ `LLM_MAX_TOKENS=*** |
| Log startup | ✅ Application startup complete |

## Catatan
- Efek samping: biaya token per pesan panjang naik sedikit.
- Test manual: minta katalog lengkap lagi dari nomor customer/pemilik, pastikan tidak terpotong.

---

# Laporan Perubahan 3: LLM_TIMEOUT 10 → 30 detik

**Tanggal:** 2026-08-21 (WIB)
**Status:** ✅ Selesai & terverifikasi

## Alasan
Dengan `LLM_MAX_TOKENS=*** generate pesan panjang (katalog) bisa >10 detik — timeout 10 detik berisiko membuat balasan gagal/kosong saat DeepSeek lambat.

## Perubahan
- `bot/.env`: `LLM_TIMEOUT` **10 → 30** detik
- Rebuild image + force-recreate container
- Tidak ada perubahan kode

## Verifikasi
| Cek | Hasil |
|---|---|
| `GET /health` | ✅ OK |
| Env di container | ✅ `LLM_TIMEOUT=*** `LLM_MAX_TOKENS=*** |

## Ringkasan env Bloomin saat ini (non-secret)
| Var | Nilai |
|---|---|
| GOWA_BASE_URL | http://gowa:3000 |
| GOWA_PUBLIC_URL | http://127.0.0.1:3000 |
| LLM_BASE_URL | https://api.deepseek.com |
| LLM_MODEL | deepseek-chat |
| LLM_TIMEOUT | 30 |
| LLM_MAX_TOKENS | *** |
| TELEGRAM_ADMIN_USER_ID | 1000715121,8209280055,7157785504 |
| CONFIG_PATH | ./config.json |
