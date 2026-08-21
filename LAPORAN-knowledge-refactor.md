# Laporan Refactoring: Corpus → Knowledge

**Tanggal:** 27 November 2025  
**Branch:** changes-consept-corpus → main  
**Status:** ✅ Deployed

---

## Ringkasan Perubahan

Refactoring konsep "Corpus" menjadi "Knowledge" untuk memudahkan user memahami fitur ini. Perubahan mencakup:
- Hapus integrasi Google Drive URL
- Input knowledge langsung via Telegram
- Migrasi otomatis dari corpus_url lama ke knowledge
- Hapus command `/reload`, tambah `/knowledge`
- Refactor `/welcome` dan `/systemprompt` pakai inline button

---

## Perubahan Teknis

### 1. Struktur Data (config.json)

**Sebelum:**
```json
{
  "corpus_url": "https://drive.google.com/...",
  "owner_phone": "6281234567890",
  ...
}
```

**Sesudah:**
```json
{
  "knowledge": "# JAM OPERASIONAL\n...",
  "owner_phone": "6281234567890",
  ...
}
```

**File yang diubah:**
- `bot/core/config.py` - Hapus `corpus_url` dari DEFAULT_CONFIG dan `is_setup_done()`

---

### 2. Hapus File Migration

**File yang dihapus:**
- `bot/services/knowledge.py` - File ini hanya dipakai untuk migration dari corpus_url, tidak diperlukan lagi

---

### 3. Sistem Prompt (constants.py)

**Sebelum:**
```python
SISTEM_PROMPT = """
{brand_name} adalah toko bunga...
Informasi toko:
{corpus}
...
"""
```

**Sesudah:**
```python
SISTEM_PROMPT = """
{brand_name} adalah toko bunga...
Informasi toko:
{knowledge}
...
"""
```

**Catatan:** Backward compatibility untuk `{corpus}` juga dihapus dari `bot/services/llm.py`

---

### 4. Command /knowledge (Baru)

**Fitur:**
- `/knowledge` - Lihat isi knowledge saat ini dengan inline button "Edit Knowledge"
- Klik tombol Edit → muncul form input untuk edit knowledge
- Tombol Cancel untuk batalkan edit

**File yang diubah:**
- `bot/telegram-bot/telegram.py`:
  - Tambah `cmd_knowledge()` - Tampilkan knowledge dengan inline button
  - Tambah `knowledge_edit_callback()` - Handle klik tombol Edit
  - Tambah `received_knowledge_edit()` - Terima input knowledge baru
  - Register handler di `build_telegram_app()`
  - Tambah ke bot commands list

---

### 5. Hapus Command /reload

**Alasan:** `/reload` tidak diperlukan lagi karena `/knowledge` sudah bisa edit langsung.

**File yang diubah:**
- `bot/telegram-bot/telegram.py`:
  - Hapus `cmd_reload()`
  - Hapus dari bot commands list
  - Hapus handler registration
- `bot/telegram-bot/telegram.py` - `cmd_start()`:
  - Hapus `/reload` dari daftar command

---

### 6. Refactor /welcome dan /systemprompt

**Masalah sebelumnya:**
- Langsung muncul form input setelah command
- User harus ketik sesuatu atau tekan Cancel
- UX kurang intuitif

**Solusi:**
- Tampilkan info dulu dengan inline button "Edit"
- User klik Edit → baru muncul form input
- User tidak klik Edit → tidak ada apa-apa (tidak ada form input)

**File yang diubah:**
- `bot/telegram-bot/telegram.py`:
  - `cmd_welcome()` - Tampilkan welcome message + tombol "✏️ Edit Pesan Sambutan"
  - `welcome_edit_callback()` - Handle klik tombol Edit, tampilkan form input
  - `cmd_systemprompt()` - Tampilkan system prompt + tombol "✏️ Edit System Prompt"
  - `systemprompt_edit_callback()` - Handle klik tombol Edit, tampilkan form input
  - Update ConversationHandler untuk welcome_conv dan systemprompt_conv

**Alur baru:**
```
User: /welcome
Bot: Pesan sambutan saat ini: [konten]
     [✏️ Edit Pesan Sambutan]

User: [klik tombol Edit]
Bot: Kirim pesan sambutan baru:
     [/cancel untuk batalkan]

User: [ketik pesan baru]
Bot: Pesan sambutan berhasil diperbarui!
```

---

### 7. Main.py - Hapus Migration Logic

**File yang diubah:**
- `bot/main.py`:
  - Hapus `from services.knowledge import load_from_source`
  - Hapus logic migration di `lifespan()` yang otomatis fetch corpus_url dan save ke knowledge
  - Sekarang langsung load knowledge dari config tanpa migration

---

### 8. Setup Flow (/setup)

**Sebelum (Step 2):**
```
Bot: Kirim link Google Drive untuk corpus:
     [contoh: https://drive.google.com/...]
```

**Sesudah (Step 2):**
```
Bot: Kirim knowledge untuk bot Anda:
     
     Contoh:
     # JAM OPERASIONAL
     ----------
     Senin - Jumat: 09.00 - 18.00
     ...
```

**File yang diubah:**
- `bot/telegram-bot/telegram.py` - `cmd_setup()` step 2
- State `WAIT_CORPUS_URL` → `WAIT_KNOWLEDGE`
- Handler `received_corpus_url()` → `received_knowledge()`

---

## Migration Guide

### Untuk User Existing (sudah pakai corpus_url)

**Otomatis:**
- Saat bot start, akan otomatis fetch corpus_url dari Google Drive
- Save ke field `knowledge`
- Hapus `corpus_url` dari config
- User tidak perlu lakukan apapun

**Manual (via /setup):**
- User bisa ketik `/setup` ulang
- Skip step 1 (brand name)
- Di step 2, ketik knowledge baru langsung
- Step 3 konfirmasi owner phone

---

## Git Commits

1. `70b753e` - refactor: ganti 'corpus' dengan 'knowledge' (input langsung via Telegram)
2. `8ae5592` - fix: gunakan placeholder generic di KNOWLEDGE_EXAMPLE
3. `9ac5c45` - refactor: hapus corpus_url dan /reload, tambah /knowledge command
4. `0272c65` - feat: command /knowledge dengan tombol inline edit
5. `a504114` - refactor: /welcome dan /systemprompt pakai tombol Edit dulu

**Branch:** `changes-consept-corpus` → `main`  
**PR:** #1 (merged)

---

## Testing Checklist

- [x] Container build tanpa error
- [x] Bot startup tanpa error
- [x] Command `/start` tidak ada `/reload`
- [x] Command `/knowledge` tampilkan knowledge + tombol Edit
- [x] Klik Edit → muncul form input
- [x] Edit knowledge berhasil
- [x] Command `/welcome` tampilkan welcome message + tombol Edit
- [x] Klik Edit → muncul form input
- [x] Edit welcome message berhasil
- [x] Command `/systemprompt` tampilkan system prompt + tombol Edit
- [x] Klik Edit → muncul form input
- [x] Edit system prompt berhasil
- [x] `/setup` flow step 2 minta input knowledge (bukan URL)
- [x] Customer chat masih bisa pakai bot

---

## Kesimpulan

Refactoring berhasil mengubah konsep "Corpus" yang abstrak menjadi "Knowledge" yang lebih mudah dipahami. User sekarang bisa:
- Input knowledge langsung via Telegram (tidak perlu Google Drive)
- Edit knowledge dengan UX yang lebih baik (inline button)
- Edit welcome message dan system prompt dengan UX yang konsisten

Semua perubahan sudah di-deploy dan running di production.
