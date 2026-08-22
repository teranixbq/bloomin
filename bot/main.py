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
    MSG_GREETINGS_CHOICE, MSG_BOT_SELECTED, MSG_PLEASE_CHOOSE,
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
_bot_enabled: bool = True

MAX_HISTORY = 10  # simpan max 10 pasang pesan (user + assistant)


def get_owner_phone() -> str:
    return load_config().get("owner_phone", "")

def get_welcome_msg() -> str:
    return load_config().get("welcome_msg", MSG_WELCOME_DEFAULT)

def set_bot_enabled(enabled: bool):
    global _bot_enabled
    _bot_enabled = enabled
    print(f"[bot] bot_enabled set to {enabled}")

def is_bot_enabled() -> bool:
    return _bot_enabled

# Track nomor yang sudah dikasih info di luar jam kerja
_notified_outside_hours: set[str] = set()
_media_forwarded_users: set[str] = set()  # Track users yang udah di-forward media

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

    # Cek apakah user sudah di-forward ke owner (spam/media/admin) - skip response
    session = sessions.get(sender_phone, {})
    if session.get("spam_forwarded") or session.get("waiting_owner") or session.get("owner_connected"):
        print(f"[handle] {sender_phone} sudah di-forward/owner session, skip response")
        return

    if sender_phone in _processing:
        print(f"[webhook] skip {sender_phone} — masih diproses")
        return

    is_new_session = sender_phone not in sessions

    if is_new_session:
        # Cek apakah yang chat adalah owner
        from core.config import load_config
        cfg = load_config()
        owner_phone = cfg.get("owner_phone", "")
        
        if sender_phone == owner_phone:
            # Owner chat langsung → langsung ke owner session, skip greetings
            start_session(sender_phone)
            session = sessions[sender_phone]
            start_owner_session(sender_phone)
            print(f"[session] owner chat langsung, skip greetings for {sender_phone}")
            return
        
        # Flow baru: Greetings dengan pilihan
        start_session(sender_phone)
        session = sessions[sender_phone]
        session["waiting_choice"] = True
        await send_message(sender_phone, MSG_GREETINGS_CHOICE)
        print(f"[session] greetings choice sent to {sender_phone}")
        return
    else:
        session = sessions.get(sender_phone, {})
        # Kalau owner connected, JANGAN reset timer - pesan user tidak boleh reset timer owner session
        if not session.get("owner_connected"):
            reset_timer(sender_phone)

    session = sessions.get(sender_phone, {})

    # Handle greetings choice (user pilih 1 atau 2)
    if session.get("waiting_choice"):
        choice = message.strip()
        if choice == "1":
            # User pilih Bot AI
            session["waiting_choice"] = False
            await send_message(sender_phone, MSG_BOT_SELECTED)
            print(f"[session] {sender_phone} chose bot mode")
            return
        elif choice == "2":
            # User pilih langsung admin - notify via WA only
            session["waiting_choice"] = False
            await send_message(sender_phone, MSG_OWNER_WAITING)
            await notify_owner(get_owner_phone(), sender_phone, "Ingin berbicara dengan admin.")
            start_owner_session(sender_phone)
            print(f"[session] {sender_phone} chose admin mode, notified via WA")
            return
        else:
            # User balas tidak jelas
            await send_message(sender_phone, MSG_PLEASE_CHOOSE)
            return

    if session.get("waiting_owner"):
        # Skip semua pesan user sampai owner balas
        print(f"[session] {sender_phone} masih waiting_owner, skip pesan user")
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
        # Kalau lagi connect owner, abaikan - biarin timer handle
        # JANGAN reset timer - pesan user tidak boleh reset timer owner session
        if session.get("owner_connected"):
            print(f"[session] {sender_phone} bilang closing tapi owner_connected, skip")
            return
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
    tg_app.bot_data["set_bot_enabled"] = set_bot_enabled
    tg_app.bot_data["is_bot_enabled"] = is_bot_enabled
    tg_app.bot_data["get_sessions"] = get_sessions
    tg_app.bot_data["cancel_timer"] = cancel_timer
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    if is_setup_done():
        cfg = load_config()
        # Load dari file dulu, fallback ke config
        knowledge_file = "/app/knowledge.txt"
        if os.path.exists(knowledge_file):
            with open(knowledge_file, "r") as f:
                _knowledge = f.read()
            print(f"[startup] knowledge loaded from {knowledge_file} ({len(_knowledge)} chars)")
        else:
            _knowledge = cfg.get("knowledge", "")
            print(f"[startup] knowledge loaded from config ({len(_knowledge)} chars)")
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
    # Gap 5: Check if bot is enabled
    if not _bot_enabled:
        print("[webhook] bot disabled, skipping message")
        return {"status": "bot_disabled"}
    
    data = await req.json()
    
    # Log full payload untuk debug multi-device routing
    print(f"[webhook] FULL PAYLOAD: {data}")
    
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
        
        # Gap 4 (Skenario 15.2): Ignore kalau user di luar jam kerja
        if user_phone in _notified_outside_hours:
            print(f"[owner_msg] {user_phone} di luar jam kerja, skip owner message")
            return {"status": "owner_msg_outside_hours"}
        
        # Skenario 15.1: Owner proactive message
        # - User baru: create owner session langsung
        # - User waiting_owner: switch ke owner_connected
        # - User session normal: force takeover ke owner session
        if user_phone not in sessions:
            start_owner_session(user_phone)
            print(f"[webhook] owner proactive: created owner session for new user {user_phone}")
        else:
            owner_connected(user_phone)
            print(f"[webhook] owner msg: connected/takeover for {user_phone}")
        
        return {"status": "owner_msg"}

    sender_raw   = payload.get("from", "")
    sender_phone = clean_phone(sender_raw)

    print(f"[webhook] sender={sender_phone} message={repr(message)} payload_keys={list(payload.keys())}")

    if sender_phone == clean_phone(get_owner_phone()):
        # Owner balas dari HP → panggil owner_connected untuk user yang waiting_owner
        sessions = get_sessions()
        chat_phone = clean_phone(chat_id)
        if sessions.get(chat_phone, {}).get("waiting_owner"):
            owner_connected(chat_phone)
        return {"status": "owner_msg"}

    # Check media FIRST - always forward to admin regardless of time
    # GOWA kirim media sebagai key langsung di payload (image, video, audio, document, dll)
    media_types = ["image", "video", "audio", "document", "sticker", "location", "contact"]
    detected_media = next((m for m in media_types if m in payload), None)
    
    if detected_media:
        cfg = load_config()
        brand_name = cfg.get("brand_name", "Bot")
        owner_phone = get_owner_phone()
        
        # Cek apakah sudah pernah forward media ke user ini
        if sender_phone not in _media_forwarded_users:
            _media_forwarded_users.add(sender_phone)
            
            # Notify user (sekali aja)
            await send_message(
                sender_phone,
                f"Maaf kak, {brand_name} AI tidak bisa membaca gambar/media 🙏\n"
                f"Saya akan alihkan ke admin."
            )
            
            # Create session first, then start owner session
            sessions = get_sessions()
            if sender_phone not in sessions:
                start_session(sender_phone)
            start_owner_session(sender_phone)
            
            # Notify WhatsApp admin
            await notify_owner(
                owner_phone,
                sender_phone,
                "Seseorang mengirim media yang tidak diketahui oleh bot"
            )
            
            print(f"[webhook] {sender_phone} sent {detected_media}, forwarded to admin")
        
        return {"status": "media_forwarded"}

    # Check waiting_owner ATAU owner_connected: skip semua pesan (PALING ATAS!)
    sessions = get_sessions()
    session = sessions.get(sender_phone, {})
    if session.get("waiting_owner") or session.get("owner_connected"):
        print(f"[webhook] {sender_phone} sedang waiting_owner/owner_connected, skip pesan")
        return {"status": "owner_session_skip"}

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
        cancel_timer(sender_phone)
        start_owner_session(sender_phone)
        session = sessions[sender_phone]
        session["spam_forwarded"] = True
        
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
