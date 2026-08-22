# Architecture & Message Flow

## 🔄 Webhook Flow Diagram

```
User kirim pesan WhatsApp
        │
        ▼
┌─────────────────────────────┐
│  1. Webhook Entry Point     │
│     - Validate event type   │
│     - Parse payload         │
│     - Check if group chat   │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  2. Owner Message Check     │
│     is_from_me = True?      │
│     sender = owner_phone?   │
│                             │
│  YES → owner_connected()    │
│        return "owner_msg"   │
└─────────────────────────────┘
        │ NO
        ▼
┌─────────────────────────────┐
│  3. Media Detection         │
│     Check payload keys:     │
│     image, video, audio,    │
│     document, sticker, etc  │
│                             │
│  Found → Forward to admin   │
│          Skip LLM           │
└─────────────────────────────┘
        │ NO
        ▼
┌─────────────────────────────┐
│  4. Outside Hours Check     │
│     Current time in work    │
│     time range?             │
│                             │
│  NO → Send info message     │
│       Add to skip set       │
│       return "outside"      │
└─────────────────────────────┘
        │ YES
        ▼
┌─────────────────────────────┐
│  5. Spam Detection          │
│     Track message times     │
│     5+ messages in 10s?     │
│                             │
│  YES → Forward to admin     │
│        Set waiting_owner    │
│        return "spam"        │
└─────────────────────────────┘
        │ NO
        ▼
┌─────────────────────────────┐
│  6. Session Management      │
│     - New session? → Start  │
│     - Existing? → Reset     │
│     - Check waiting states  │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  7. Message Handler         │
│     - Check keywords        │
│     - Check greetings       │
│     - Call LLM              │
│     - Send response         │
└─────────────────────────────┘
```

## 📦 Webhook Payload Structure (GOWA)

```json
{
  "event": "message",
  "payload": {
    "id": "message_id",
    "from": "628123456789@s.whatsapp.net",
    "from_name": "John Doe",
    "chat_id": "628123456789@s.whatsapp.net",
    "body": "Halo, saya mau tanya",
    "is_from_me": false,
    "timestamp": 1234567890,
    "sender_display_name": "John",
    "image": {...},  // Optional - only if media
    "video": {...},  // Optional - only if media
    "document": {...} // Optional - only if media
  }
}
```

**Key Point:** Media detection based on **payload keys**, NOT `message_type` field.

## 🎯 State Machine

```
                    ┌──────────────┐
                    │   IDLE       │
                    │  (No Session)│
                    └──────┬───────┘
                           │ User message
                           ▼
                    ┌──────────────┐
         ┌─────────│   ACTIVE     │◄────────────┐
         │         │              │             │
         │         └──────┬───────┘             │
         │                │                      │
         │    ┌───────────┼───────────┐         │
         │    │           │           │         │
         ▼    ▼           ▼           ▼         │
   ┌─────────┐   ┌──────────────┐  ┌──────────┐│
   │ WAITING │   │   WAITING    │  │ WAITING  ││
   │ CONFIRM │   │    OWNER     │  │  ADMIN   ││
   │         │   │              │  │ CONFIRM  ││
   └─────────┘   └──────┬───────┘  └──────────┘│
         │                │                      │
         │                │ Owner replies        │
         │                ▼                      │
         │         ┌──────────────┐             │
         └────────►│   OWNER      │─────────────┘
                   │  CONNECTED   │   Admin session
                   │              │   ends, back to
                   └──────┬───────┘   normal flow
                          │
                          │ 5 min timeout
                          ▼
                   ┌──────────────┐
                   │   CLOSED     │
                   └──────────────┘
```

## 🔄 State Transitions

### IDLE → ACTIVE
**Trigger:** User mengirim pesan pertama  
**Action:** 
- Create session
- Send welcome message
- Start inactivity timer (5 min)

### ACTIVE → WAITING_CONFIRM
**Trigger:** Inactivity timer expired (5 min tanpa pesan)  
**Action:**
- Send "Masih di sini?" message
- Start close wait timer (2 min)

### WAITING_CONFIRM → ACTIVE
**Trigger:** User membalas pesan  
**Action:**
- Reset inactivity timer
- Continue normal conversation

### WAITING_CONFIRM → CLOSED
**Trigger:** Close wait timer expired (2 min tanpa reply)  
**Action:**
- Send goodbye message
- Delete session

### ACTIVE → WAITING_OWNER
**Trigger:** 
- User kirim media
- User spam (5+ pesan dalam 10 detik)
- User minta admin (setelah konfirmasi)

**Action:**
- Send "Forwarding to admin" message
- Cancel inactivity timer
- Start owner timeout timer (5 min)
- Notify admin via WhatsApp

### WAITING_OWNER → OWNER_CONNECTED
**Trigger:** Admin membalas pesan di WhatsApp  
**Action:**
- Cancel owner timeout timer
- Start inactivity timer (5 min)
- Set `owner_connected = True`
- Reset `waiting_owner = False`

### OWNER_CONNECTED → CLOSED
**Trigger:** Inactivity timer expired (5 min tanpa pesan dari user/admin)  
**Action:**
- Send goodbye message
- Delete session

### ACTIVE → WAITING_ADMIN_CONFIRM
**Trigger:** User ketik keyword "admin" atau minta bicara dengan admin  
**Action:**
- Send konfirmasi "Mau dihubungkan ke admin?"
- Tunggu jawaban ya/tidak

### WAITING_ADMIN_CONFIRM → WAITING_OWNER
**Trigger:** User jawab "ya"  
**Action:**
- Notify admin
- Start owner session

### WAITING_ADMIN_CONFIRM → ACTIVE
**Trigger:** User jawab "tidak"  
**Action:**
- Continue normal conversation

## 🛡️ Special Handling

### 1. Outside Hours Skip
```python
# Set tracking (no session overhead)
_notified_outside_hours: set[str] = set()

# Logic:
if not is_within_work_time():
    if sender_phone not in _notified_outside_hours:
        _notified_outside_hours.add(sender_phone)
        await send_message(sender_phone, get_work_time_info())
    return "outside_hours"

# Lazy reset saat masuk jam kerja
if _notified_outside_hours:
    _notified_outside_hours.clear()
```

### 2. Media Auto-Forward
```python
# Detect media dari payload keys
media_types = ["image", "video", "audio", "document", "sticker"]
detected_media = next((m for m in media_types if m in payload), None)

if detected_media:
    # Create session (jika belum ada)
    if sender_phone not in sessions:
        start_session(sender_phone)
    
    # Start owner session
    start_owner_session(sender_phone)
    
    # Notify admin
    await notify_owner(owner_phone, sender_phone, "Media received")
    
    # Tell user
    await send_message(sender_phone, "Forwarding ke admin...")
```

### 3. Spam Detection
```python
# Track message timestamps per user
if not hasattr(webhook, '_message_times'):
    webhook._message_times = {}

now = time.time()
# Keep only last 10 seconds
webhook._message_times[sender_phone] = [
    t for t in webhook._message_times[sender_phone]
    if now - t < 10
]
webhook._message_times[sender_phone].append(now)

# Check if 5+ messages in 10 seconds
if len(webhook._message_times[sender_phone]) >= 5:
    # Forward to admin
    # Same logic as media forward
```

### 4. Owner Connection Detection
```python
# Check 1: Message dari owner (is_from_me)
if is_from_me:
    user_phone = clean_phone(chat_id)
    if sessions.get(user_phone, {}).get("waiting_owner"):
        owner_connected(user_phone)
    return "owner_msg"

# Check 2: Owner balas dari HP (sender = owner_phone)
if sender_phone == clean_phone(get_owner_phone()):
    chat_phone = clean_phone(chat_id)
    if sessions.get(chat_phone, {}).get("waiting_owner"):
        owner_connected(chat_phone)
    return "owner_msg"
```

### 5. Closing Keyword Ignore (Saat Owner Connected)
```python
if _is_closing(message):
    # Skip closing jika owner masih connected
    if session.get("owner_connected"):
        reset_timer(sender_phone)
        return
    
    # Normal closing
    await close_session(sender_phone, send_goodbye=True)
```

## 📊 Timer Management

### Inactivity Timer (Normal Session)
```python
SESSION_INACTIVITY = 300  # 5 minutes

async def _inactivity_timer(phone: str):
    await asyncio.sleep(SESSION_INACTIVITY)
    # Send "Masih di sini?"
    await send_message(phone, MSG_STILL_THERE)
    # Wait 2 more minutes
    await asyncio.sleep(SESSION_CLOSE_WAIT)
    # Auto-close
    await close_session(phone)
```

### Owner Timeout Timer
```python
SESSION_OWNER_TIMEOUT = 300  # 5 minutes

async def _owner_session_timer(phone: str):
    await asyncio.sleep(SESSION_OWNER_TIMEOUT)
    session = _sessions.get(phone)
    if not session.get("owner_connected"):
        # Admin tidak balas
        await send_message(phone, MSG_OWNER_TIMEOUT)
    else:
        # Admin balas tapi sudah 5 min tanpa activity
        await send_message(phone, MSG_CLOSING)
    await close_session(phone)
```

## 🎨 LLM Integration

### System Prompt Structure
```python
system_prompt = f"""
You are a helpful assistant for {brand_name}.
Answer based on the provided information only.
If you don't know, reply: "Maaf, saya tidak tahu. Silakan hubungi admin."

Knowledge Base:
{knowledge}
"""
```

### Conversation History
```python
# Store last 5 exchanges (10 messages)
session["history"] = [
    {"role": "user", "content": "Berapa harga mawar?"},
    {"role": "assistant", "content": "Mawar merah Rp 50.000/batang"},
    {"role": "user", "content": "Ada warna lain?"},
    {"role": "assistant", "content": "Ada putih dan pink juga kak"},
    # ... max 10 messages
]

# Send to LLM
messages = [
    {"role": "system", "content": system_prompt},
    *session["history"],
    {"role": "user", "content": current_message}
]
```

## 🚀 Performance Optimization

1. **Lazy Reset** - Outside hours set di-clear saat masuk jam kerja (bukan per-user check)
2. **Set Tracking** - Gunakan set untuk skip nomor (O(1) lookup)
3. **No Session Overhead** - Outside hours tidak create session
4. **Async Tasks** - Timers jalan parallel tanpa blocking
5. **Payload Key Detection** - Media detection tanpa JSON parsing

---

**Next:** [Scenarios](scenarios.md) - Contoh kasus nyata dengan step-by-step
