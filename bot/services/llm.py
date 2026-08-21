import os
import httpx
from core.config import load_config

LLM_API_KEY    = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL   = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL      = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT    = float(os.getenv("LLM_TIMEOUT", "10"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "300"))

def _get_system_prompt(knowledge: str) -> str:
    cfg = load_config()
    template = cfg.get("system_prompt", "")
    brand_name = cfg.get("brand_name", "Bloomin")
    filled = template.replace("{brand_name}", brand_name)
    if "{knowledge}" in filled:
        return filled.format(knowledge=knowledge)
    if "{corpus}" in filled:  # template lama yang belum diupdate
        return filled.format(corpus=knowledge)
    return filled + f"\n\n{knowledge}"

async def ask_llm(knowledge: str, query: str, history: list[dict] | None = None) -> str | None:
    if not LLM_API_KEY:
        return None

    system = _get_system_prompt(knowledge)

    # Build messages: system + history (max 10 terakhir) + query terbaru
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": query})

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "max_tokens": LLM_MAX_TOKENS,
                    "messages": messages,
                },
            )

        data = resp.json()
        if "error" in data:
            code = data["error"].get("code", 0)
            print(f"[llm] error code={code}: {data['error'].get('message','')[:80]}")
            return None

        content = data["choices"][0]["message"]["content"].strip()
        print(f"[llm] ok model={LLM_MODEL} tokens={data.get('usage',{}).get('total_tokens',0)}")
        return content

    except httpx.TimeoutException:
        print("[llm] timeout")
        return None
    except Exception as e:
        print(f"[llm] exception: {e}")
        return None

async def generate_welcome_msg(knowledge: str, brand_name: str) -> str | None:
    if not LLM_API_KEY:
        return None

    prompt = (
        f"Berdasarkan informasi toko berikut, buat pesan sambutan WhatsApp yang singkat dan menarik.\n\n"
        f"Aturan:\n"
        f"- Gunakan nama brand: {brand_name}\n"
        f"- Sebutkan 3-5 topik yang bisa ditanyakan customer berdasarkan isi knowledge\n"
        f"- Format WhatsApp: bold pakai *teks*, list pakai • bullet\n"
        f"- Akhiri dengan \"Ketik /admin kalau ingin langsung bicara dengan admin kami 😊\"\n"
        f"- Maksimal 10 baris\n"
        f"- Jangan terlalu formal, gunakan bahasa ramah\n\n"
        f"Informasi toko:\n{knowledge}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

        data = resp.json()
        if "error" in data:
            print(f"[generate_welcome] error: {data['error'].get('message','')[:80]}")
            return None

        content = data["choices"][0]["message"]["content"].strip()
        print(f"[generate_welcome] ok, {len(content)} chars")
        return content

    except Exception as e:
        print(f"[generate_welcome] exception: {e}")
        return None
