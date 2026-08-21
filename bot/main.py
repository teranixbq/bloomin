import os
import sys
import importlib
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from services.corpus import load_corpus
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

load_dotenv()

# Folder telegram-bot punya hyphen, tidak bisa di-import sebagai module biasa
telegram_module = importlib.import_module("telegram-bot.telegram")
build_telegram_app = telegram_module.build_telegram_app

_corpus: str | None = None
_processing: set[str] = set()

MAX_HISTORY = 10  # simpan max 10 pasang pesan (user + assistant)


def get_owner_phone() -> str:
    return load_config().get("owner_phone", "")

def get_welcome_msg() -> str:
    return load_config().get("welcome_msg", MSG_WELCOME_DEFAULT)

def _set_corpus(text: str):
    global _corpus
    _corpus = text

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


async def _handle_message(sender_phone: str, message: str):
    sessions = get_sessions()

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
        answer = await ask_llm(_corpus, message, history)

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

        await send_message(sender_phone, answer)

    finally:
        _processing.discard(sender_phone)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _corpus

    tg_app = build_telegram_app()
    tg_app.bot_data["set_corpus"] = _set_corpus
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    if is_setup_done():
        cfg = load_config()
        _corpus = load_corpus(cfg["corpus_url"])
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

    print(f"[webhook] sender={sender_phone} message={repr(message)}")

    if sender_phone == clean_phone(get_owner_phone()):
        return {"status": "ignored"}

    if not message:
        return {"status": "empty"}

    if _corpus is None:
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
        "corpus_chars": len(_corpus) if _corpus else 0,
        "corpus_url": cfg.get("corpus_url", ""),
        "owner_phone": cfg.get("owner_phone", ""),
        "active_sessions": len(get_sessions()),
    }
