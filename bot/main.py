import os
import sys
import importlib
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from services.llm import ask_llm
from services.session import (
    get_sessions, start_session, reset_timer, close_session,
    start_owner_session, owner_connected, cancel_timer,
)
from core.notif import send_message, notify_owner
from core.config import load_config, is_setup_done
from core.constants import (
    MSG_WELCOME_DEFAULT, MSG_LLM_ERROR, MSG_TIDAK_TAHU,
    MSG_ADMIN_CONFIRM, MSG_ADMIN_CONFIRM_NO, MSG_ADMIN_CONFIRM_UNCLEAR,
    MSG_ACTIVE_SESSION_GREETING, MSG_NOT_READY,
    MSG_OWNER_WAITING, MSG_CLOSING,
    CLOSING_KEYWORDS, ADMIN_KEYWORDS, YES_KEYWORDS, NO_KEYWORDS,
    GREETINGS_REPLY,
)
from datetime import datetime, time
import pytz

load_dotenv()

# Folder telegram-bot punya hyphen, tidak bisa di-import sebagai module biasa
telegram_module = importlib.import_module("telegram-bot.telegram")
build_telegram_app = telegram_module.build_telegram_app

_knowledge: str | None = None
_processing: set[str] = set()

MAX_HISTORY = 10  # simpan max 10 pasang pesan (user + assistant)


def get_owner_phone() -> str:
    return load_config().get("owner_phone", "")

def get_welcome_msg() -> str:
    return load_config().get("welcome_msg", MSG_WELCOME_DEFAULT)

# Track nomor yang sudah dikasih info di luar jam kerja
_notified_outside_hours = set()

def _set_knowledge(text: str):
    global _knowledge
    _knowledge = text

def _is_closing(message: str) -> bool:
    normalized = message.lower().strip().rstrip("!.,")
    if normalized in CLOSING_KEYWORDS:
        return True
    return any(kw in normalized for kw in CLOSING_KEYWORDS)

def _has_admin_keyword(message: str) -> bool:
    normalized = message.lower()
    return any(kw in normalized for kw in ADMIN_KEYWORDS)

def clean_phone(raw: str) -> str:
    return raw.split("@")[0]

def is_within_work_time() -> bool:
    """Check apakah waktu sekarang dalam jam kerja"""
    cfg = load_config()
    work_time = cfg.get("work_time", {"open": "08:00", "close": "17:00"})
    
    try:
        tz = pytz.timezone("Asia/Jakarta")
        now = datetime.now(tz).time()
        
        open_time = datetime.strptime(work_time["open"], "%H:%M").time()
        close_time = datetime.strptime(work_time["close"], "%H:%M").time()
        
        return open_time <= now <= close_time
    except Exception as e:
        print(f"[work_time] Error checking work time: {e}")
        return True  # Default ke True jika ada error

def get_work_time_info() -> str:
    """Get info jam kerja untuk pesan di luar jam kerja"""
    cfg = load_config()
    work_time = cfg.get("work_time", {"open": "08:00", "close": "17:00"})
    brand_name = cfg.get("brand_name", "Bloomin")
    return f"Terima kasih telah menghubungi {brand_name}. Saat ini di luar jam operasional kami ({work_time['open']} - {work_time['close']} WIB). Pesan Anda akan kami balas besok saat jam buka. 😊"


async def _handle_message(sender_phone: str, message: str):
    sessions = get_sessions()

    # Check jam kerja
    if not is_within_work_time():
        # Di luar jam kerja - pakai set tracking (no session overhead)
        if sender_phone not in _notified_outside_hours:
            # Pesan pertama di luar jam kerja
            _notified_outside_hours.add(sender_phone)
            print(f"[worktime] {sender_phone} di luar jam kerja, kirim info")
            await send_message(sender_phone, get_work_time_info())
        else:
            # Udah di set, skip (bot mati)
            print(f"[worktime] {sender_phone} masih di luar jam kerja, skip")
        return
    
    # Masuk jam kerja → clear entire set (lazy reset)
    if _notified_outside_hours:
        _notified_outside_hours.clear()
        print("[worktime] Jam kerja dimulai, reset outside hours skip set")

    if sender_phone in _processing:
        print(f"[webhook] skip {sender_phone} — masih diproses")
        return

    is_new_session = sender_phone not in sessions

    if is_new_session:
        start_session(sender_phone)
        await send_message(sender_phone, get_welcome_msg())
        return
    else:
        reset_timer(sender_phone)

    session = sessions.get(sender_phone, {})

    if session.get("waiting_owner"):
        owner_connected(sender_phone)
        if _is_closing(message):
            await close_session(sender_phone, send_goodbye=True, msg=MSG_CLOSING)
        return

    if session.get("waiting_admin_confirm"):
        norm = message.lower().strip().rstrip("!.,")
        if norm in YES_KEYWORDS:
            session["waiting_admin_confirm"] = False
            await notify_owner(get_owner_phone(), sender_phone, "Ingin berbicara dengan admin.")
            await send_message(sender_phone, MSG_OWNER_WAITING)
            start_owner_session(sender_phone)
        elif norm in NO_KEYWORDS:
            session["waiting_admin_confirm"] = False
            await send_message(sender_phone, MSG_ADMIN_CONFIRM_NO)
        else:
            await send_message(sender_phone, MSG_ADMIN_CONFIRM_UNCLEAR)
        return

    if _is_closing(message):
        await close_session(sender_phone, send_goodbye=True, msg=MSG_CLOSING)
        return

    if _has_admin_keyword(message):
        session["waiting_admin_confirm"] = True
        await send_message(sender_phone, MSG_ADMIN_CONFIRM)
        return

    stripped = message.lower().strip().rstrip("!.,?")
    if stripped in GREETINGS_REPLY:
        await send_message(sender_phone, MSG_ACTIVE_SESSION_GREETING)
        return

    _processing.add(sender_phone)
    try:
        history = session.get("history", [])
        answer = await ask_llm(_knowledge, message, history)

        if answer is None:
            await send_message(sender_phone, MSG_LLM_ERROR)
            await close_session(sender_phone, send_goodbye=False)
            return

        if "TIDAK_TAHU" in answer.strip():
            session["waiting_admin_confirm"] = True
            await send_message(sender_phone, MSG_TIDAK_TAHU)
            return

        # Simpan history per-sesi (sliding window MAX_HISTORY pasang)
        session["history"].append({"role": "user", "content": message})
        session["history"].append({"role": "assistant", "content": answer})
        if len(session["history"]) > MAX_HISTORY * 2:
            session["history"] = session["history"][-(MAX_HISTORY * 2):]

        # Tambahkan credit ke setiap response AI (pakai brand name)
        cfg = load_config()
        brand_name = cfg.get("brand_name", "").strip() or "Bot AI"
        answer_with_credit = f"{answer}\n\n*_{brand_name} AI_*"
        await send_message(sender_phone, answer_with_credit)

    finally:
        _processing.discard(sender_phone)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _knowledge

    tg_app = build_telegram_app()
    tg_app.bot_data["set_knowledge"] = _set_knowledge
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    if is_setup_done():
        cfg = load_config()
        _knowledge = cfg.get("knowledge", "")
    else:
        admin_ids = [
            int(x.strip())
            for x in os.getenv("TELEGRAM_ADMIN_USER_ID", "0").split(",")
            if x.strip()
        ]
        for admin_id in admin_ids:
            try:
                await tg_app.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        "Bot baru saja restart dan konfigurasi tidak ditemukan.\n\n"
                        "Ketik /setup untuk melakukan konfigurasi ulang."
                    )
                )
            except Exception as e:
                print(f"[telegram] Gagal kirim notifikasi reset ke {admin_id}: {e}")

    yield

    sessions = get_sessions()
    for phone in list(sessions.keys()):
        cancel_timer(phone)
    sessions.clear()

    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()

    if data.get("event") != "message":
        return {"status": "ignored"}

    payload    = data.get("payload", {})
    is_from_me = payload.get("is_from_me", False)
    chat_id    = payload.get("chat_id", "")
    message    = payload.get("body", "").strip()

    if chat_id.endswith("@g.us"):
        return {"status": "ignored"}

    if is_from_me:
        user_phone = clean_phone(chat_id)
        sessions = get_sessions()
        if sessions.get(user_phone, {}).get("waiting_owner"):
            owner_connected(user_phone)
        return {"status": "owner_msg"}

    sender_raw   = payload.get("from", "")
    sender_phone = clean_phone(sender_raw)

    print(f"[webhook] sender={sender_phone} message={repr(message)} payload_keys={list(payload.keys())}")

    if sender_phone == clean_phone(get_owner_phone()):
        return {"status": "ignored"}

    # Check media FIRST - always forward to admin regardless of time
    message_type = payload.get("message_type", "")
    if message_type in ["image", "video", "audio", "document", "sticker", "location", "contact"]:
        cfg = load_config()
        brand_name = cfg.get("brand_name", "Bot")
        owner_phone = get_owner_phone()
        
        # Notify user
        await send_message(
            sender_phone,
            f"Maaf kak, {brand_name} AI tidak bisa membaca gambar/media 🙏\n"
            f"Saya akan alihkan ke admin."
        )
        
        # Create session if not exists, then set waiting_owner
        sessions = get_sessions()
        if sender_phone not in sessions:
            start_session(sender_phone)
        session = sessions[sender_phone]
        cancel_timer(sender_phone)
        session["waiting_owner"] = True
        session["owner_connected"] = False
        session["timer"] = asyncio.create_task(_owner_session_timer(sender_phone))
        
        # Notify admin
        await notify_owner(
            owner_phone,
            sender_phone,
            "Seseorang mengirim media yang tidak diketahui oleh bot"
        )
        
        print(f"[webhook] {sender_phone} sent {message_type}, forwarded to admin")
        return {"status": "media_forwarded"}

    # Check outside hours (text messages only)
    if not is_within_work_time():
        if sender_phone not in _notified_outside_hours:
            _notified_outside_hours.add(sender_phone)
            print(f"[worktime] {sender_phone} di luar jam kerja, kirim info")
            await send_message(sender_phone, get_work_time_info())
        else:
            print(f"[worktime] {sender_phone} masih di luar jam kerja, skip")
        return {"status": "outside_hours"}
    
    # Masuk jam kerja → clear entire set (lazy reset)
    if _notified_outside_hours:
        _notified_outside_hours.clear()
        print("[worktime] Jam kerja dimulai, reset outside hours skip set")

    # Spam detection: track message timestamps
    import time
    if not hasattr(webhook, '_message_times'):
        webhook._message_times = {}
    
    now = time.time()
    if sender_phone not in webhook._message_times:
        webhook._message_times[sender_phone] = []
    
    # Keep only last 10 seconds of messages
    webhook._message_times[sender_phone] = [
        t for t in webhook._message_times[sender_phone] 
        if now - t < 10
    ]
    webhook._message_times[sender_phone].append(now)
    
    # Check if spam (5+ messages in 10 seconds)
    if len(webhook._message_times[sender_phone]) >= 5:
        cfg = load_config()
        brand_name = cfg.get("brand_name", "Bot")
        owner_phone = get_owner_phone()
        
        # Cek apakah sudah pernah di-forward ke admin
        sessions = get_sessions()
        if sender_phone in sessions and sessions[sender_phone].get("spam_forwarded"):
            # Sudah di-forward, skip semua pesan berikutnya
            print(f"[spam] {sender_phone} sudah di-forward ke admin, skip")
            return {"status": "spam_skip"}
        
        # Notify user
        await send_message(
            sender_phone,
            f"Hai kak, sepertinya kakak mengirim banyak pesan berturut-turut 😊\n"
            f"Saya akan alihkan ke admin {brand_name} untuk membantu."
        )
        
        # Create session dan set waiting_owner (sama kayak media forwarding)
        if sender_phone not in sessions:
            start_session(sender_phone)
        session = sessions[sender_phone]
        cancel_timer(sender_phone)
        session["waiting_owner"] = True
        session["owner_connected"] = False
        session["spam_forwarded"] = True
        session["timer"] = asyncio.create_task(_owner_session_timer(sender_phone))
        
        # Notify admin
        await notify_owner(
            owner_phone,
            sender_phone,
            "Seseorang melakukan pesan berturut-turut/spamming, coba lihat apa yang dia tanya"
        )
        
        print(f"[spam] {sender_phone} sent {len(webhook._message_times[sender_phone])} messages in 10s, forwarded to admin")
        return {"status": "spam_forwarded"}

    if not message:
        return {"status": "empty"}

    if _knowledge is None:
        await send_message(sender_phone, MSG_NOT_READY)
        return {"status": "not_ready"}

    asyncio.create_task(_handle_message(sender_phone, message))
    return {"status": "ok"}


@app.get("/health")
async def health():
    cfg = load_config()
    return {
        "status": "ok",
        "setup_done": is_setup_done(),
        "knowledge_chars": len(_knowledge) if _knowledge else 0,
        "owner_phone": cfg.get("owner_phone", ""),
        "active_sessions": len(get_sessions()),
    }
