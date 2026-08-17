import os
import httpx
from core.config import load_config
from core.constants import MSG_OWNER_NOTIF

GOWA_BASE_URL = os.getenv("GOWA_BASE_URL", "")
GOWA_BASIC_AUTH = os.getenv("GOWA_BASIC_AUTH", "")

def _gowa_auth() -> httpx.BasicAuth | None:
    if not GOWA_BASIC_AUTH or ":" not in GOWA_BASIC_AUTH:
        return None
    user, passwd = GOWA_BASIC_AUTH.split(":", 1)
    return httpx.BasicAuth(user, passwd)

async def send_message(phone: str, message: str) -> bool:
    device_id = load_config().get("device_id", "")
    if not device_id:
        raise RuntimeError("device_id belum ada di config. Lakukan /qr dulu di Telegram.")

    url     = f"{GOWA_BASE_URL}/send/message"
    payload = {"phone": phone, "message": message}
    headers = {"X-Device-Id": device_id}

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, auth=_gowa_auth(), timeout=10)
        print(f"[send_message] to={phone} status={resp.status_code} body={resp.text[:100]}")
        resp.raise_for_status()
        return True

async def send_image(phone: str, image_url: str, caption: str = "") -> bool:
    device_id = load_config().get("device_id", "")
    if not device_id:
        raise RuntimeError("device_id belum ada di config.")

    url     = f"{GOWA_BASE_URL.rstrip('/api/v1')}/send/image"
    payload = {"phone": phone, "image_url": image_url, "caption": caption}
    headers = {"X-Device-Id": device_id}

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, auth=_gowa_auth(), timeout=10)
        print(f"[send_image] to={phone} status={resp.status_code} body={resp.text[:100]}")
        resp.raise_for_status()
        return True

async def notify_owner(owner_phone: str, sender_phone: str, question: str):
    msg = MSG_OWNER_NOTIF.format(sender_phone=sender_phone, question=question)
    try:
        await send_message(owner_phone, msg)
    except Exception as e:
        print(f"[notify_owner] gagal kirim WA: {e}")
