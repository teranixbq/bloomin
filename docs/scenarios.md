# Scenarios - Bloomin' AI Bot

Dokumen ini berisi semua skenario yang sudah diimplementasikan dalam bot, dengan contoh flow step-by-step.

---

## 1. GREETINGS & ROUTING (Entry Point)

### Skenario 1.1: User Chat Pertama Kali (Greetings)
**Kondisi:** Jam kerja (08:00-17:00), user pertama kali chat

**Flow:**
```
1. User: [Kirim pesan pertama - apapun]
   ↓
2. Bot: Create session baru
   - greetings_sent = True
   - waiting_choice = True
   - Timer inactivity 5 menit dimulai
   ↓
3. Bot: "Halo kak! 👋
         
         Selamat datang di Bloomin'!
         Mau ngobrol sama siapa nih?
         
         🤖 Ketik 1 - Tanya ke Bot AI (produk, harga, dll)
         👤 Ketik 2 - Langsung ke Admin"
   ↓
4. [Menunggu user pilih 1 atau 2]
```

### Skenario 1.2: User Pilih "1" (Bot AI)
**Kondisi:** User balas "1" setelah greetings

**Flow:**
```
1. User: "1"
   - waiting_choice = False
   - bot_mode = True
   ↓
2. Bot: "Oke kak! Silakan tanya apa aja tentang produk kami ya 😊
         (misal: harga buket, jenis bunga, cara pesan, dll)"
   ↓
3. User: "Bloom Box harganya berapa?"
   ↓
4. Bot: Call LLM dengan knowledge base
   ↓
5. Bot: [Jawab dari knowledge]
   - Timer reset 5 menit
```

### Skenario 1.3: User Pilih "2" (Langsung Admin)
**Kondisi:** User balas "2" setelah greetings

**Flow:**
```
1. User: "2"
   - waiting_choice = False
   - waiting_owner = True
   - owner_connected = False
   - Timer owner timeout 5 menit dimulai
   ↓
2. Bot: "Baik kak, saya sambungkan ke admin ya. Mohon tunggu sebentar 🙏"
   ↓
3. Bot: Send notif ke admin via Telegram
   - "🔔 Notifikasi Admin
    Dari: [Nama User]
    Nomor: [Nomor User]
    Pesan: Ingin langsung ke admin."
   ↓
4. [Menunggu admin balas dari WhatsApp]
```

**Setelah ini, flow sama kayak Skenario 3.2 (admin balas) atau 3.3 (admin tidak balas)**

### Skenario 1.4: User Langsung Tanya (Tanpa Pilih)
**Kondisi:** User kirim pertanyaan langsung tanpa pilih 1 atau 2

**Flow:**
```
1. User: [Kirim pesan pertama]
   ↓
2. Bot: [Greetings seperti Skenario 1.1]
   ↓
3. User: "Harga buket mawar berapa?" (bukan "1" atau "2")
   ↓
4. Bot: "Eits, pilih dulu ya kak 😊
         
         Ketik 1 untuk tanya ke Bot AI
         Ketik 2 untuk langsung ke Admin"
   - waiting_choice tetap True
   ↓
5. [Menunggu user pilih 1 atau 2]
```

### Skenario 1.5: User Reply Tidak Jelas
**Kondisi:** User balas selain "1" atau "2" saat waiting_choice

**Flow:**
```
1. User: [Kirim pesan pertama]
   ↓
2. Bot: [Greetings]
   ↓
3. User: "halo" / "ya" / "mau tanya" / [apapun selain "1" atau "2"]
   ↓
4. Bot: "Maaf kak, pilih 1 atau 2 ya 😊
         
         1 = Tanya ke Bot AI
         2 = Langsung ke Admin"
   - waiting_choice tetap True
   ↓
5. [Menunggu pilihan valid]
```

---

## 2. OUTSIDE HOURS (Di Luar Jam Kerja)

### Skenario 2.1: User Chat di Luar Jam Kerja (Pertama Kali)
**Kondisi:** User chat jam 20:00 (di luar 08:00-17:00)

**Flow:**
```
1. User: "Halo"
   ↓
2. Bot: "Halo kak! 🌸
         
         Saat ini kami sedang di luar jam operasional.
         Jam buka kami:
         Senin-Sabtu: 08:00-17:00 WIB
         Minggu & Libur: Tutup
         
         Silakan chat kembali di jam operasional ya kak! 
         Pesan kakak akan kami balas secepatnya saat kami buka kembali. 😊"
   - User ditambahkan ke set _notified_outside_hours
   - Tidak create session
   ↓
3. [Selesai, tidak ada follow-up]
```

### Skenario 2.2: User Chat Lagi di Luar Jam Kerja
**Kondisi:** User yang sama chat lagi masih di luar jam kerja

**Flow:**
```
1. User: "Halo, masih buka?"
   ↓
2. [Bot cek: user ada di _notified_outside_hours?]
   ↓
3. [YA - User sudah pernah dinotifikasi]
   - Skip, tidak kirim pesan apapun
   - Tidak create session
   ↓
4. [Selesai, silent]
```

### Skenario 2.3: Lazy Reset Saat Masuk Jam Kerja
**Kondisi:** Jam 08:01 (masuk jam kerja), user chat

**Flow:**
```
1. [Jam 08:01 - masuk jam kerja]
   ↓
2. Bot: Clear set _notified_outside_hours (lazy reset)
   ↓
3. User: "Halo"
   ↓
4. Bot: Create session, proses normal (kayak Skenario 1.1)
```

---

## 3. ADMIN CONNECTION (Minta Bicara dengan Admin)

### Skenario 3.1: User Minta Admin (Keyword Detection)
**Kondisi:** User chat mengandung keyword "admin", "seller", "penjual"

**Flow:**
```
1. User: "Saya mau ngomong sama admin dong"
   ↓
2. Bot: "Baik kak, untuk berbicara dengan admin/seller, 
         apakah kakak yakin ingin saya sambungkan? (ya/tidak)"
   - waiting_admin_confirm = True
   ↓
3. User: "Ya"
   - waiting_admin_confirm = False
   - waiting_owner = True
   - owner_connected = False
   - Timer owner timeout 5 menit dimulai
   ↓
4. Bot: "Baik kak, saya akan segera menghubungi admin kami. 
         Mohon ditunggu ya kak! 😊"
   ↓
5. Bot: Send notif ke admin via Telegram
   - "🔔 Notifikasi Admin
    Dari: [Nama User]
    Nomor: [Nomor User]
    Pesan: Ingin berbicara dengan admin."
   ↓
6. [Menunggu admin balas dari WhatsApp]
```

### Skenario 3.2: Admin Balas (Positive Flow)
**Kondisi:** Admin balas dari WhatsApp dalam 5 menit

**Flow:**
```
1. [Previous: User minta admin, waiting_owner = True]
   ↓
2. Admin balas dari WhatsApp: "Halo kak, ada yang bisa saya bantu?"
   ↓
3. Bot: Detect owner_connected = True
   - Cancel timer owner timeout
   - waiting_owner = False
   - owner_connected = True
   - Switch ke timer inactivity 5 menit
   ↓
4. [User dan admin saling balas]
   - Setiap pesan OWNER reset timer 5 menit
   - Pesan user TIDAK reset timer
   ↓
5. [5 menit tidak ada pesan dari owner]
   ↓
6. Bot: "Terima kasih sudah menghubungi kami! 🌸
         Kalau ada pertanyaan lagi, jangan ragu untuk chat kami kembali ya kak."
   - Session dihapus langsung (tanpa tanya "masih di sini?")
```

### Skenario 3.3: Admin Tidak Balas (Negative Flow)
**Kondisi:** Admin tidak balas dalam 5 menit

**Flow:**
```
1. [Previous: User minta admin, waiting_owner = True]
   ↓
2. [5 menit berlalu, admin tidak balas]
   ↓
3. Bot: "Mohon maaf kak, admin kami sedang tidak bisa dihubungi saat ini. 🙏
         
         Silakan coba lagi nanti atau tinggalkan pesan, 
         kami akan segera menghubungi kakak kembali."
   - Session dihapus
```

### Skenario 3.4: User Batal Minta Admin
**Kondisi:** User jawab "tidak" saat ditanya konfirmasi

**Flow:**
```
1. User: "Saya mau ngomong sama admin"
   ↓
2. Bot: "Baik kak, untuk berbicara dengan admin/seller, 
         apakah kakak yakin ingin saya sambungkan? (ya/tidak)"
   ↓
3. User: "Tidak, ga jadi deh"
   - waiting_admin_confirm = False
   ↓
4. Bot: "Baik kak, kalau ada pertanyaan lain silakan tanya saja ya! 😊"
   - Continue normal conversation
```

### Skenario 3.5: User Jawab Ambigu
**Kondisi:** User jawab selain "ya" atau "tidak"

**Flow:**
```
1. User: "Saya mau ngomong sama admin"
   ↓
2. Bot: "Baik kak, untuk berbicara dengan admin/seller, 
         apakah kakak yakin ingin saya sambungkan? (ya/tidak)"
   ↓
3. User: "Mungkin"
   ↓
4. Bot: "Maaf kak, silakan jawab 'ya' atau 'tidak' saja ya 😊"
   - waiting_admin_confirm masih True
```

---

## 4. MEDIA FORWARDING

### Skenario 4.1: User Kirim Gambar
**Kondisi:** User kirim foto/gambar

**Flow:**
```
1. User: [Kirim gambar]
   ↓
2. Bot: Detect media dari payload keys (image, video, audio, document, sticker)
   ↓
3. Bot: Create session (jika belum ada)
   - waiting_owner = True
   - owner_connected = False
   - Timer owner timeout 5 menit dimulai
   ↓
4. Bot: "Gambar/media kakak sudah saya teruskan ke admin kami. 
         Mohon ditunggu ya kak! 😊"
   ↓
5. Bot: Send notif ke admin via Telegram
   - "🔔 Notifikasi Admin
    Dari: [Nama User]
    Nomor: [Nomor User]
    Media: [Jenis media yang dikirim]"
   ↓
6. [Menunggu admin balas dari WhatsApp]
```

**Setelah ini, flow sama kayak Skenario 3.2 (admin balas) atau 3.3 (admin tidak balas)**

### Skenario 4.2: User Kirim Video
**Kondisi:** User kirim video

**Flow:** Sama kayak Skenario 4.1, tapi detect key "video"

### Skenario 4.3: User Kirim Dokumen
**Kondisi:** User kirim file dokumen (PDF, DOC, dll)

**Flow:** Sama kayak Skenario 4.1, tapi detect key "document"

### Skenario 4.4: User Kirim Sticker
**Kondisi:** User kirim sticker WhatsApp

**Flow:** Sama kayak Skenario 4.1, tapi detect key "sticker"

---

## 5. SPAM DETECTION

### Skenario 5.1: User Spam (5+ Pesan dalam 10 Detik)
**Kondisi:** User kirim 5 atau lebih pesan dalam 10 detik

**Flow:**
```
1. User: [Kirim 5+ pesan berturut-turut dalam 10 detik]
   ↓
2. Bot: Detect spam (track message timestamps per user)
   - Hitung pesan dalam 10 detik terakhir
   - Jika >= 5 pesan → trigger spam
   ↓
3. Bot: Cek apakah sudah pernah di-forward (spam_forwarded flag)
   ↓
4. [Belum pernah di-forward]
   - Create session (jika belum ada)
   - waiting_owner = True
   - owner_connected = False
   - spam_forwarded = True
   - Timer owner timeout 5 menit dimulai
   ↓
5. Bot: "Sepertinya kakak mengirim banyak pesan sekaligus ya 😅
         Saya akan langsung sambungkan ke admin kami.
         Mohon ditunggu ya kak!"
   ↓
6. Bot: Send notif ke admin via Telegram
   - "🔔 Notifikasi Admin
    Dari: [Nama User]
    Nomor: [Nomor User]
    Pesan: [5+ pesan berturut-turut]"
   ↓
7. [Menunggu admin balas dari WhatsApp]
```

**Setelah ini, flow sama kayak Skenario 3.2 (admin balas) atau 3.3 (admin tidak balas)**

### Skenario 5.2: User Spam Lagi (Sudah Pernah Di-forward)
**Kondisi:** User yang sama spam lagi setelah pernah di-forward

**Flow:**
```
1. User: [Kirim 5+ pesan lagi dalam 10 detik]
   ↓
2. Bot: Detect spam
   ↓
3. Bot: Cek spam_forwarded flag
   ↓
4. [Sudah pernah di-forward]
   - Skip, tidak kirim pesan apapun
   - Tidak notif admin lagi
   ↓
5. [Selesai, silent]
```

---

## 6. CLOSING KEYWORD

### Skenario 6.1: User Bilang Terima Kasih (Normal Session)
**Kondisi:** User bilang "terima kasih", "makasih", "thanks", dll saat normal session

**Flow:**
```
1. User: "Oke makasih ya infonya"
   ↓
2. Bot: Detect closing keyword
   - Cek apakah owner_connected = False
   ↓
3. [owner_connected = False - normal session]
   ↓
4. Bot: "Sama-sama kak! 🌸
         Senang bisa membantu.
         Kalau ada pertanyaan lagi, jangan ragu untuk chat kami kembali ya!
         Selamat beraktivitas! 😊"
   - Session dihapus
```

### Skenario 6.2: User Bilang Terima Kasih (Saat Owner Connected)
**Kondisi:** User bilang "terima kasih" saat owner_connected = True

**Flow:**
```
1. [Previous: Admin sudah connect, sedang ngobrol]
   ↓
2. User: "Oke makasih ya udah dibantu"
   ↓
3. Bot: Detect closing keyword
   - Cek apakah owner_connected = True
   ↓
4. [owner_connected = True - skip closing]
   - TIDAK reset timer (timer cuma reset dari pesan owner)
   - Tidak close session
   - Biarkan pesan user diteruskan ke owner via WhatsApp
   ↓
5. [Timer terus berjalan sampai habis]
   ↓
6. [5 menit tanpa pesan owner] → MSG_CLOSING → Session close
```

**Kenapa skip?** Karena owner masih connected. Pesan user (termasuk "terima kasih") diteruskan ke owner tanpa intervensi bot. Timer inactivity tetap berjalan — hanya pesan OWNER yang bisa reset timer. Session ditutup otomatis saat owner berhenti balas.

---

## 7. GREETING DETECTION

### Skenario 7.1: User Sapa Pertama Kali
**Kondisi:** User kirim greeting di pesan pertama

**Flow:**
```
1. User: "Halo selamat pagi"
   ↓
2. Bot: Detect greeting keyword ("halo", "hai", "hi", "selamat pagi", dll)
   ↓
3. Bot: "Halo kak! 👋 Selamat pagi juga!
         
         Saya [Nama Brand] AI Assistant, siap membantu kakak.
         Ada yang bisa saya bantu hari ini?"
   - Session created
   - Timer inactivity 5 menit dimulai
   ↓
4. [Continue normal conversation]
```

### Skenario 7.2: User Sapa Setelah Session Aktif
**Kondisi:** User kirim greeting saat session sudah aktif

**Flow:**
```
1. [Previous conversation...]
   ↓
2. User: "Oh iya halo lagi"
   ↓
3. Bot: Process via LLM (greeting detection tidak berlaku untuk pesan ke-2+)
   ↓
4. Bot: [Response dari LLM berdasarkan konteks]
```

---

## 8. KNOWLEDGE BASE MANAGEMENT

### Skenario 8.1: Admin Download Knowledge Base
**Kondisi:** Admin ketik /knowledge di Telegram

**Flow:**
```
1. Admin: /knowledge
   ↓
2. Bot: Baca file /app/knowledge.txt
   ↓
3. Bot: Kirim file knowledge.txt ke admin
   - Caption: "Ini knowledge base yang aktif saat ini. 
               Edit file ini lalu upload balik untuk update."
```

### Skenario 8.2: Admin Update Knowledge Base
**Kondisi:** Admin upload file knowledge.txt yang sudah diedit

**Flow:**
```
1. Admin: [Upload file knowledge.txt]
   ↓
2. Bot: Validate file
   - Check ekstensi .txt
   - Check nama file "knowledge.txt"
   ↓
3. [Valid]
   - Replace /app/knowledge.txt
   - Reload knowledge ke memory
   ↓
4. Bot: "✅ Knowledge base berhasil diupdate!"
   - Bot sekarang pakai knowledge baru
```

### Skenario 8.3: Admin Upload File Salah
**Kondisi:** Admin upload file yang bukan .txt atau nama salah

**Flow:**
```
1. Admin: [Upload file data.pdf]
   ↓
2. Bot: Validate file
   ↓
3. [Invalid - bukan .txt atau nama bukan "knowledge.txt"]
   ↓
4. Bot: "❌ File tidak valid!
         
         Pastikan:
         - Ekstensi file: .txt
         - Nama file: knowledge.txt"
```

---

## 9. TELEGRAM ADMIN COMMANDS

### Skenario 9.1: Admin Cek Status Bot
**Kondisi:** Admin ketik /status di Telegram

**Flow:**
```
1. Admin: /status
   ↓
2. Bot: Collect system info
   - Uptime
   - Memory usage
   - Active sessions count
   - Knowledge base status
   ↓
3. Bot: "📊 Status Bot
         
         ✅ Bot aktif
         🕐 Uptime: 2 jam 15 menit
         💾 Memory: 45 MB
         👥 Active sessions: 3
         📚 Knowledge base: Loaded (150 entries)"
```

### Skenario 9.2: Admin Force Close Session
**Kondisi:** Admin mau tutup session user manual

**Flow:**
```
1. Admin: /close 081234567890
   ↓
2. Bot: Cek session untuk nomor tersebut
   ↓
3. [Session ada]
   - Close session
   - Hapus dari memory
   ↓
4. Bot: "✅ Session untuk 081234567890 berhasil ditutup"
```

### Skenario 9.3: Admin List Active Sessions
**Kondisi:** Admin mau lihat semua session aktif

**Flow:**
```
1. Admin: /sessions
   ↓
2. Bot: List semua active sessions
   ↓
3. Bot: "👥 Active Sessions (3)
         
         1. 081234567890 - Budi
            Status: Normal conversation
            Last activity: 2 menit lalu
         
         2. 081987654321 - Siti
            Status: Waiting owner
            Last activity: 1 menit lalu
         
         3. 081112223334 - Ahmad
            Status: Owner connected
            Last activity: 30 detik lalu"
```

---

## 10. EDGE CASES

### Skenario 10.1: User Kirim Pesan Kosong
**Kondisi:** User kirim pesan tanpa text (cuma spasi/enter)

**Flow:**
```
1. User: [Kirim pesan kosong]
   ↓
2. Bot: Detect empty message
   ↓
3. Bot: "Maaf kak, saya tidak bisa membaca pesan kakak. 
         Bisa tolong kirim ulang? 😊"
```

### Skenario 10.2: Knowledge Base Belum Loaded
**Kondisi:** Bot baru start, knowledge base belum selesai load

**Flow:**
```
1. User: "Halo"
   ↓
2. Bot: Cek _knowledge is None
   ↓
3. Bot: "Mohon maaf, sistem kami sedang mempersiapkan diri. 
         Silakan coba lagi dalam beberapa saat ya kak! 🙏"
```

### Skenario 10.3: LLM Error
**Kondisi:** Call ke LLM gagal (timeout, error, dll)

**Flow:**
```
1. User: "Ada buket mawar?"
   ↓
2. Bot: Call LLM
   ↓
3. [LLM error/timeout]
   ↓
4. Bot: "Mohon maaf kak, sistem kami sedang mengalami kendala teknis. 🙏
         Silakan coba lagi dalam beberapa saat, 
         atau hubungi admin kami langsung di [nomor admin]."
```

### Skenario 10.4: User Kirim Voice Note
**Kondisi:** User kirim voice message

**Flow:**
```
1. User: [Kirim voice note]
   ↓
2. Bot: Detect audio media
   ↓
3. Bot: "Maaf kak, saat ini saya belum bisa memproses pesan suara. 
         Bisa tolong ketik pesan kakak? 😊"
   - Tidak forward ke admin
   - Tidak create session
```

---

## 11. TIMER MANAGEMENT

### Timer Types:

1. **Inactivity Timer (5 menit)**
   - Digunakan untuk: Normal conversation, owner connected session
   - Reset untuk normal session: Setiap USER kirim pesan
   - Reset untuk owner session: HANYA saat OWNER kirim pesan (pesan user TIDAK reset)
   - Expired untuk normal session: Kirim "Masih di sini?" → tunggu 2 menit → close
   - Expired untuk owner session: LANGSUNG kirim "Terima kasih" → close (TANPA "Masih di sini?")

2. **Owner Timeout Timer (5 menit)**
   - Digunakan untuk: Menunggu admin balas (media/spam/admin request)
   - Reset: Tidak bisa reset, cuma bisa cancel
   - Expired: Kirim "Admin tidak bisa dihubungi" → close

3. **Close Wait Timer (2 menit)**
   - Digunakan untuk: Setelah "Masih di sini?"
   - Reset: Kalau user balas
   - Expired: Kirim closing message → close

### Timer Flow Examples:

**Normal Conversation:**
```
User chat → Inactivity timer start (5 min)
↓
User chat lagi → Timer reset (5 min lagi)
↓
[5 menit diam] → "Masih di sini?" → Close wait timer start (2 min)
↓
User balas → Close wait cancel, Inactivity timer reset (5 min)
↓
[5 menit diam lagi] → "Masih di sini?" → Close wait timer (2 min)
↓
[2 menit diam] → Closing message → Session close
```

**Waiting for Owner:**
```
User minta admin → Owner timeout timer start (5 min)
↓
[5 menit admin tidak balas] → "Admin tidak bisa dihubungi" → Session close
```

**Owner Connected:**
```
User minta admin → Owner timeout timer start (5 min)
↓
Admin balas (dalam 5 menit) → Owner timeout cancel, Inactivity timer start (5 min)
↓
Owner chat → Timer reset setiap pesan owner (pesan user TIDAK reset)
↓
[5 menit tidak ada pesan owner] → LANGSUNG MSG_CLOSING → Session close
(TIDAK ADA "Masih di sini?" di owner session)
```

---

## 12. STATE TRANSITIONS

```
=== NORMAL FLOW ===

IDLE (No Session)
  ↓ [User chat]
ACTIVE (Normal Conversation)
  ↓ [5 menit diam]
WAITING_CONFIRM ("Masih di sini?")
  ↓ [User balas]
ACTIVE
  ↓ [2 menit diam]
CLOSED (Session dihapus)

=== ADMIN CONNECTION ===

ACTIVE
  ↓ [User minta admin]
WAITING_ADMIN_CONFIRM ("Yakin mau sambung ke admin?")
  ↓ [User: "Ya"]
WAITING_OWNER (Menunggu admin balas)
  ↓ [Admin balas]
OWNER_CONNECTED (Admin & user ngobrol)
  ↓ [5 menit tanpa pesan OWNER]
CLOSED (Langsung kirim MSG_CLOSING, TIDAK ADA "Masih di sini?")

=== OWNER PROACTIVE (NEW) ===

IDLE
  ↓ [Owner chat ke user di worktime]
OWNER_CONNECTED (Langsung, tanpa WAITING_OWNER)
  ↓ [5 menit tanpa pesan owner]
CLOSED

ACTIVE
  ↓ [Owner chat ke user - force take over]
OWNER_CONNECTED (Langsung, tanpa WAITING_ADMIN_CONFIRM)
  ↓ [5 menit tanpa pesan owner]
CLOSED

=== ADMIN TIMEOUT ===

WAITING_OWNER
  ↓ [5 menit admin tidak balas]
CLOSED (Langsung close, kirim "Admin tidak bisa dihubungi")
```

---

## 14. COMMON ISSUES & SOLUTIONS

### Issue 1: Bot tidak balas
**Penyebab:** 
- Knowledge base belum loaded
- LLM error
- Session corrupt

**Solusi:** 
- Tunggu beberapa detik, coba lagi
- Cek log bot untuk error
- Restart container jika perlu

### Issue 2: Admin tidak dapat notif
**Penyebab:**
- Telegram bot token invalid
- Admin chat ID salah
- Telegram API error

**Solusi:**
- Cek config.json (telegram_bot_token, admin_chat_id)
- Test manual kirim pesan ke bot Telegram
- Cek log untuk error

### Issue 3: Session tidak close otomatis
**Penyebab:**
- Timer cancel tapi tidak start ulang
- Async task stuck

**Solusi:**
- Restart container
- Clear semua session manual via Telegram /clearsessions

### Issue 4: Media tidak ter-forward
**Penyebab:**
- GOWA payload structure berubah
- Media detection logic salah

**Solusi:**
- Cek log untuk payload yang diterima
- Update media detection di webhook

---

## 15. OWNER PROACTIVE MESSAGE (NEW - Proposed)

### Skenario 15.1: Owner Chat ke User di Worktime
**Kondisi:** Owner proaktif chat ke nomor user saat jam kerja (dengan atau tanpa session aktif)

**Flow:**
```
1. Owner kirim pesan ke nomor user
   ↓
2. Bot detect: sender = owner phone
   ↓
3. Bot cek: user punya session aktif?
   ↓
4. [Belum ada session - user baru atau session sudah close]
   - Create session baru untuk user
   - Langsung set owner_connected = True
   - Timer inactivity 5 menit dimulai
   ↓
5. [Ada session aktif - user sedang chat bot/waiting owner]
   - Panggil owner_connected()
   - Switch ke inactivity timer 5 menit
   ↓
6. Langsung masuk Scenario 3.2 (owner connected session)
```

**Contoh 1 - User baru:**
```
Owner: "Halo kak Budi, pesanan buketnya sudah siap ya"
Bot: [Silent - langsung owner session]
Owner: "Bisa diambil hari ini jam 3 sore"
Bot: [Silent - timer reset 5 menit]
[5 menit owner tidak chat lagi]
Bot → ke user: "Terima kasih sudah menghubungi kami! 🌸"
```

**Contoh 2 - User sedang chat bot:**
```
User: "Saya mau tanya harga buket mawar"
Bot: "Harga buket mawar mulai dari Rp 150.000..."
Owner: "Halo kak, saya admin. Ada yang bisa dibantu?"
Bot: [Silent - switch ke owner session]
Owner: "Untuk buket mawar premium kita ada promo"
Bot: [Silent - timer reset 5 menit]
[5 menit owner tidak chat lagi]
Bot → ke user: "Terima kasih sudah menghubungi kami! 🌸"
```

**Catatan:** Ini adalah skenario "force take over" — owner ambil alih percakapan secara langsung. Setelah owner selesai, session langsung close. Kalau user mau chat lagi, mulai dari awal (greetings + LLM).

### Skenario 15.2: Owner Balas di Luar Jam Kerja → Ignore
**Kondisi:** User sudah dapat pesan "di luar jam kerja", kemudian owner balas ke user tersebut

**Flow:**
```
1. [Previous: User chat di luar jam kerja]
   - Bot sudah kirim pesan outside hours
   - User sudah masuk set _notified_outside_hours
   ↓
2. Owner balas ke user tersebut
   ↓
3. Bot detect: sender = owner phone
   - Cek: user ada di _notified_outside_hours?
   ↓
4. [YA - user sudah dinotifikasi outside hours]
   - Abaikan pesan owner
   - Tidak create session
   - Tidak kirim notif ke user
   ↓
5. [Selesai, silent]
```

**Kenapa ignore?**
- User sudah di-inform bahwa ini di luar jam kerja
- Kalau bot forward pesan owner ke user, nanti user bingung karena sebelumnya dibilang tutup
- Konsistensi: di luar jam = bot off, semua interaksi di-skip

---
