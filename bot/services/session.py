import asyncio
from core.notif import send_message
from core.constants import (
    SESSION_INACTIVITY, SESSION_CLOSE_WAIT, SESSION_OWNER_TIMEOUT,
    MSG_STILL_THERE, MSG_CLOSING, MSG_TIMEOUT_CLOSE, MSG_OWNER_TIMEOUT,
)

_sessions: dict[str, dict] = {}


def get_sessions() -> dict[str, dict]:
    return _sessions

def cancel_timer(phone: str):
    session = _sessions.get(phone)
    if session and session.get("timer"):
        session["timer"].cancel()
        session["timer"] = None

async def close_session(phone: str, send_goodbye: bool = True, msg: str = None):
    cancel_timer(phone)
    _sessions.pop(phone, None)
    if send_goodbye:
        await send_message(phone, msg or MSG_CLOSING)
    print(f"[session] closed for {phone}")

async def _inactivity_timer(phone: str):
    try:
        await asyncio.sleep(SESSION_INACTIVITY)
        session = _sessions.get(phone)
        if not session:
            return
        
        # Outside hours session - just remove silently after 3 minutes
        if session.get("outside_hours"):
            _sessions.pop(phone, None)
            print(f"[session] outside hours session expired for {phone}")
            return
        
        # Waiting owner - kirim MSG_OWNER_TIMEOUT (owner gak balas)
        if session.get("waiting_owner"):
            await send_message(phone, MSG_OWNER_TIMEOUT)
            _sessions.pop(phone, None)
            print(f"[session] waiting_owner timeout, closed for {phone}")
            return
        
        # Owner connected session - LANGSUNG close tanpa tanya "masih di sini?"
        if session.get("owner_connected"):
            await send_message(phone, MSG_CLOSING)
            _sessions.pop(phone, None)
            print(f"[session] owner session inactivity, closed for {phone}")
            return
        
        # Normal session - ada flow "Masih di sini?" → tunggu 2 menit → close
        session["waiting_confirm"] = True
        session["timer"] = None
        await send_message(phone, MSG_STILL_THERE)
        print(f"[session] inactivity ping sent to {phone}")
        await asyncio.sleep(SESSION_CLOSE_WAIT)
        session = _sessions.get(phone)
        if session and session.get("waiting_confirm"):
            await send_message(phone, MSG_TIMEOUT_CLOSE)
            _sessions.pop(phone, None)
            print(f"[session] auto-closed (no response) for {phone}")
    except asyncio.CancelledError:
        pass

def reset_timer(phone: str):
    cancel_timer(phone)
    session = _sessions.get(phone)
    if session:
        session["waiting_confirm"] = False
        session["timer"] = asyncio.create_task(_inactivity_timer(phone))

async def _owner_session_timer(phone: str):
    try:
        await asyncio.sleep(SESSION_OWNER_TIMEOUT)
        session = _sessions.get(phone)
        if not session or not session.get("waiting_owner"):
            return
        if session.get("owner_connected"):
            await send_message(phone, MSG_CLOSING)
        else:
            await send_message(phone, MSG_OWNER_TIMEOUT)
        _sessions.pop(phone, None)
        print(f"[session] owner session timeout, closed for {phone}")
    except asyncio.CancelledError:
        pass

def start_owner_session(phone: str):
    cancel_timer(phone)
    session = _sessions.get(phone)
    if session:
        session["waiting_owner"] = True
        session["owner_connected"] = False
        session["timer"] = asyncio.create_task(_owner_session_timer(phone))
    print(f"[session] owner session started for {phone}")

def owner_connected(phone: str):
    session = _sessions.get(phone)
    if session and session.get("waiting_owner"):
        cancel_timer(phone)
        session["waiting_owner"] = False      # ✅ Reset
        session["owner_connected"] = True
        session["timer"] = asyncio.create_task(_inactivity_timer(phone))  # ✅ Ganti timer
        print(f"[session] owner connected, switch to normal conversation for {phone}")

def start_session(phone: str, outside_hours: bool = False):
    _sessions[phone] = {
        "timer": asyncio.create_task(_inactivity_timer(phone)),
        "waiting_confirm": False,
        "waiting_admin_confirm": False,
        "waiting_choice": False,  # ✅ Baru: menunggu user pilih 1 atau 2
        "waiting_owner": False,
        "owner_connected": False,
        "outside_hours": outside_hours,
        "history": [],
    }
    print(f"[session] started for {phone}{' (outside hours)' if outside_hours else ''}")
