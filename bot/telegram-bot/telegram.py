import os
import asyncio
import httpx
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from core.config import load_config, save_config

TELEGRAM_BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_USER_ID = int(os.getenv("TELEGRAM_ADMIN_USER_ID", "0"))
GOWA_BASE_URL          = os.getenv("GOWA_BASE_URL", "http://gowa:3000")

GOWA_PUBLIC_URL = os.getenv("GOWA_PUBLIC_URL", "")
GOWA_BASIC_AUTH = os.getenv("GOWA_BASIC_AUTH", "")

def gowa_auth() -> httpx.BasicAuth | None:
    """Return BasicAuth untuk semua request ke GOWA, atau None jika tidak dikonfigurasi."""
    if not GOWA_BASIC_AUTH or ":" not in GOWA_BASIC_AUTH:
        return None
    user, passwd = GOWA_BASIC_AUTH.split(":", 1)
    return httpx.BasicAuth(user, passwd)

WAIT_CORPUS_URL, WAIT_OWNER_PHONE, WAIT_BRAND_NAME = range(3)
WAIT_EDIT_WELCOME, WAIT_EDIT_SYSTEMPROMPT = range(3, 5)

def is_admin(update: Update) -> bool:
    return update.effective_user.id == TELEGRAM_ADMIN_USER_ID

def get_device_id() -> str:
    """Ambil device_id dari config.json."""
    cfg = load_config()
    return cfg.get("device_id", "")

async def ensure_device() -> str:
    """
    Pastikan device sudah ada di GOWA. Jika belum, buat device baru.
    Return device_id.
    """
    device_id = get_device_id()
    if device_id:
        # Verifikasi device masih ada
        try:
            async with httpx.AsyncClient(auth=gowa_auth()) as client:
                resp = await client.get(
                    f"{GOWA_BASE_URL}/devices",
                    timeout=10,
                )
                if resp.status_code == 200:
                    return device_id
        except Exception:
            pass

    # Buat device baru
    async with httpx.AsyncClient(auth=gowa_auth()) as client:
        resp = await client.post(
            f"{GOWA_BASE_URL}/devices",
            json={"name": "Sapamin-Admin"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    new_id = data.get("results", {}).get("id", "")
    if not new_id:
        raise RuntimeError(f"Gagal membuat device GOWA: {data}")

    cfg = load_config()
    cfg["device_id"] = new_id
    save_config(cfg)
    return new_id

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    if not cfg.get("is_setup_done"):
        await update.message.reply_text(
            "Selamat datang di Sapamin Bot Manager!\n\n"
            "Setup belum selesai. Ketik /setup untuk memulai konfigurasi."
        )
    else:
        await update.message.reply_text(
            "Sapamin Bot Manager\n\n"
            "Perintah tersedia:\n"
            "/setup - Konfigurasi bot (brand, corpus, owner)\n"
            "/qr - Login WhatsApp via QR code\n"
            "/status - Cek status koneksi WhatsApp\n"
            "/config - Lihat konfigurasi saat ini\n"
            "/welcome - Edit pesan sambutan bot\n"
            "/systemprompt - Edit system prompt LLM\n"
            "/reload - Reload corpus dari Google Drive\n"
            "/restart - Restart koneksi WhatsApp\n"
            "/logout - Logout session WhatsApp"
        )

def _skip_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ Skip", callback_data="setup_skip"),
        InlineKeyboardButton("❌ Cancel", callback_data="setup_cancel"),
    ]])

async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    current_brand = cfg.get("brand_name", "Sapamin")
    await update.message.reply_text(
        "Setup Bot\n\n"
        f"Langkah 1/3: Kirim nama brand toko kamu.\n\n"
        f"Nilai saat ini: {current_brand}\n"
        "Kirim nama baru atau tekan Skip untuk mempertahankan.",
        reply_markup=_skip_cancel_keyboard(),
    )
    return WAIT_BRAND_NAME

async def received_brand_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END

    # Handle callback dari tombol inline
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "setup_cancel":
            await query.edit_message_text("Setup dibatalkan.")
            return ConversationHandler.END
        elif query.data == "setup_skip":
            cfg = load_config()
            brand_name = cfg.get("brand_name", "Sapamin")
            context.user_data["brand_name"] = brand_name
            current_url = cfg.get("corpus_url", "-")
            await query.edit_message_text(
                f"Brand dipertahankan: {brand_name}\n\n"
                "Langkah 2/3: Kirim URL Google Drive untuk file corpus toko.\n\n"
                f"Nilai saat ini: {current_url}\n"
                "Kirim URL baru atau tekan Skip untuk mempertahankan.",
                reply_markup=_skip_cancel_keyboard(),
            )
            return WAIT_CORPUS_URL

    brand_name = update.message.text.strip()
    if len(brand_name) < 2 or len(brand_name) > 50:
        await update.message.reply_text(
            "Nama brand tidak valid. Harus antara 2-50 karakter.\nCoba lagi:",
            reply_markup=_skip_cancel_keyboard(),
        )
        return WAIT_BRAND_NAME

    context.user_data["brand_name"] = brand_name
    cfg = load_config()
    current_url = cfg.get("corpus_url", "-")
    await update.message.reply_text(
        f"Nama brand: {brand_name}\n\n"
        "Langkah 2/3: Kirim URL Google Drive untuk file corpus toko.\n\n"
        f"Nilai saat ini: {current_url}\n"
        "Kirim URL baru atau tekan Skip untuk mempertahankan.",
        reply_markup=_skip_cancel_keyboard(),
    )
    return WAIT_CORPUS_URL

async def received_corpus_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "setup_cancel":
            await query.edit_message_text("Setup dibatalkan.")
            return ConversationHandler.END
        elif query.data == "setup_skip":
            cfg = load_config()
            url = cfg.get("corpus_url", "-")
            context.user_data["corpus_url"] = url
            current_phone = cfg.get("owner_phone", "-")
            await query.edit_message_text(
                f"Corpus URL dipertahankan.\n\n"
                "Langkah 3/3: Kirim nomor WhatsApp owner untuk menerima notifikasi.\n\n"
                f"Nilai saat ini: {current_phone}\n"
                "Kirim nomor baru atau tekan Skip untuk mempertahankan.",
                reply_markup=_skip_cancel_keyboard(),
            )
            return WAIT_OWNER_PHONE

    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text(
            "URL tidak valid. Harus dimulai dengan https://\nCoba lagi:",
            reply_markup=_skip_cancel_keyboard(),
        )
        return WAIT_CORPUS_URL

    context.user_data["corpus_url"] = url
    cfg = load_config()
    current_phone = cfg.get("owner_phone", "-")
    await update.message.reply_text(
        "URL corpus tersimpan.\n\n"
        "Langkah 3/3: Kirim nomor WhatsApp owner untuk menerima notifikasi.\n\n"
        f"Nilai saat ini: {current_phone}\n"
        "Kirim nomor baru atau tekan Skip untuk mempertahankan.",
        reply_markup=_skip_cancel_keyboard(),
    )
    return WAIT_OWNER_PHONE

async def _finalize_setup(message, context, corpus_url: str, brand_name: str, phone: str):
    cfg = load_config()
    cfg["corpus_url"]    = corpus_url
    cfg["owner_phone"]   = phone
    cfg["brand_name"]    = brand_name
    cfg["is_setup_done"] = True
    save_config(cfg)

    await message.reply_text("Memuat corpus dari URL yang diberikan...")
    try:
        from services.corpus import load_corpus
        from services.llm import generate_welcome_msg
        corpus_text = load_corpus(corpus_url)
        set_corpus = context.application.bot_data.get("set_corpus")
        if set_corpus:
            set_corpus(corpus_text)

        await message.reply_text("Generating pesan sambutan dari corpus...")
        welcome_msg = await generate_welcome_msg(corpus_text, brand_name)
        if welcome_msg:
            cfg = load_config()
            cfg["welcome_msg"] = welcome_msg
            save_config(cfg)

        await message.reply_text(
            f"Konfigurasi tersimpan!\n\n"
            f"Brand: {brand_name}\n"
            f"Corpus URL: {corpus_url}\n"
            f"Nomor Owner: {phone}\n"
            f"Corpus: {len(corpus_text)} karakter\n\n"
            + (f"Pesan sambutan:\n{welcome_msg}\n\n" if welcome_msg else "Pesan sambutan menggunakan default.\n\n")
            + "Langkah selanjutnya: ketik /qr untuk login WhatsApp.\n"
              "Bot belum aktif sampai QR di-scan."
        )
    except Exception as e:
        await message.reply_text(
            f"Gagal memuat corpus: {e}\n"
            "Periksa URL Google Drive dan pastikan file bisa diakses publik.\n"
            "Ketik /setup untuk coba lagi."
        )
        cfg["is_setup_done"] = False
        save_config(cfg)

async def received_owner_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END

    cfg = load_config()

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "setup_cancel":
            await query.edit_message_text("Setup dibatalkan.")
            return ConversationHandler.END
        elif query.data == "setup_skip":
            phone      = cfg.get("owner_phone", "")
            corpus_url = context.user_data.get("corpus_url", cfg.get("corpus_url", ""))
            brand_name = context.user_data.get("brand_name", cfg.get("brand_name", "Sapamin"))
            await query.edit_message_text(f"Nomor owner dipertahankan: {phone}")
            await _finalize_setup(query.message, context, corpus_url, brand_name, phone)
            return ConversationHandler.END

    phone = update.message.text.strip()
    if not phone.startswith("62") or not phone.isdigit():
        await update.message.reply_text(
            "Format nomor tidak valid. Harus diawali 62 dan hanya angka.\n"
            "Contoh: 628123456789\n\nCoba lagi:",
            reply_markup=_skip_cancel_keyboard(),
        )
        return WAIT_OWNER_PHONE

    corpus_url = context.user_data.get("corpus_url", cfg.get("corpus_url", ""))
    brand_name = context.user_data.get("brand_name", cfg.get("brand_name", "Sapamin"))
    await _finalize_setup(update.message, context, corpus_url, brand_name, phone)
    return ConversationHandler.END

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    await update.message.reply_text("Setup dibatalkan.")
    return ConversationHandler.END

def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data="edit_cancel"),
    ]])

async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    welcome_msg = cfg.get("welcome_msg", "")
    await update.message.reply_text(
        f"Pesan sambutan saat ini:\n\n{welcome_msg}\n\n"
        "Kirim pesan baru untuk mengubah.",
        reply_markup=_cancel_keyboard(),
    )
    return WAIT_EDIT_WELCOME

async def received_welcome_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Dibatalkan.")
        return ConversationHandler.END
    new_msg = update.message.text.strip()
    cfg = load_config()
    cfg["welcome_msg"] = new_msg
    save_config(cfg)
    await update.message.reply_text(
        f"Pesan sambutan berhasil diperbarui!\n\nPreview:\n{new_msg}"
    )
    return ConversationHandler.END

async def cmd_systemprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    system_prompt = cfg.get("system_prompt", "")
    msg = f"System prompt LLM saat ini:\n\n{system_prompt}"
    if len(msg) > 4000:
        await update.message.reply_text(msg[:4000])
        await update.message.reply_text(
            msg[4000:] + "\n\nKirim system prompt baru untuk mengubah.",
            reply_markup=_cancel_keyboard(),
        )
    else:
        await update.message.reply_text(
            msg + "\n\nKirim system prompt baru untuk mengubah.",
            reply_markup=_cancel_keyboard(),
        )
    return WAIT_EDIT_SYSTEMPROMPT

async def received_system_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Dibatalkan.")
        return ConversationHandler.END
    new_prompt = update.message.text.strip()
    cfg = load_config()
    cfg["system_prompt"] = new_prompt
    save_config(cfg)
    await update.message.reply_text("System prompt LLM berhasil diperbarui!")
    return ConversationHandler.END

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Dibatalkan.")
    else:
        await update.message.reply_text("Dibatalkan.")
    return ConversationHandler.END

async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    await update.message.reply_text(
        f"Konfigurasi saat ini:\n\n"
        f"Setup selesai: {'Ya' if cfg.get('is_setup_done') else 'Belum'}\n"
        f"Corpus URL: {cfg.get('corpus_url') or '-'}\n"
        f"Nomor Owner: {cfg.get('owner_phone') or '-'}\n"
        f"Device ID: {cfg.get('device_id') or '-'}\n\n"
        "Ketik /setup untuk mengubah konfigurasi."
    )

async def cmd_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        device_id = await ensure_device()

        # Cek apakah sudah terhubung
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            status_resp = await client.get(
                f"{GOWA_BASE_URL}/devices/{device_id}/status", timeout=10
            )
        status = status_resp.json().get("results", {})

        if status.get("is_logged_in"):
            if status.get("is_connected"):
                await update.message.reply_text(
                    "WhatsApp sudah terhubung dan aktif.\n"
                    "Gunakan /logout dulu jika ingin login dengan akun lain."
                )
            else:
                # Session ada tapi disconnect — coba reconnect
                await update.message.reply_text("Session ditemukan, mencoba reconnect...")
                async with httpx.AsyncClient(auth=gowa_auth()) as client:
                    await client.post(
                        f"{GOWA_BASE_URL}/devices/{device_id}/reconnect", timeout=15
                    )
                await update.message.reply_text(
                    "Reconnect dikirim. Gunakan /status untuk cek koneksi.\n"
                    "Jika masih tidak terhubung, gunakan /logout lalu /qr."
                )
            return

        await update.message.reply_text("Membuat QR code...")

        # Panggil /login — GOWA generate QR dan langsung return qr_link ke PNG
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            login_resp = await client.get(
                f"{GOWA_BASE_URL}/devices/{device_id}/login", timeout=60
            )
        login_data = login_resp.json()
        results = login_data.get("results", {})
        qr_link = results.get("qr_link", "")
        qr_duration = results.get("qr_duration", 30)

        if not qr_link:
            # Sudah login atau error
            msg = login_data.get("message", "")
            await update.message.reply_text(
                f"Tidak bisa generate QR: {msg}\n"
                "Coba /logout dulu lalu /qr lagi."
            )
            return

        # qr_link menggunakan localhost — ganti ke GOWA_BASE_URL internal agar bisa diakses dari container bot
        qr_url_internal = qr_link.replace("http://localhost:3000", GOWA_BASE_URL)

        # Download PNG dari GOWA
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            img_resp = await client.get(qr_url_internal, timeout=15)
        img_resp.raise_for_status()

        # Kirim gambar QR ke Telegram, simpan message untuk dihapus nanti
        qr_message = await update.message.reply_photo(
            photo=img_resp.content,
            caption=(
                f"Scan QR code ini di WhatsApp kamu.\n"
                f"QR berlaku {qr_duration} detik.\n\n"
                "Buka WhatsApp > Perangkat Tertaut > Tautkan Perangkat"
            )
        )

        # Event untuk koordinasi antara delete_after dan poll_connected
        connected_event = asyncio.Event()

        # Hapus pesan QR setelah expired, kecuali sudah connected
        async def delete_after(seconds: int):
            try:
                await asyncio.wait_for(connected_event.wait(), timeout=float(seconds))
                # connected → hapus pesan QR tanpa kirim notif expired
                try:
                    await qr_message.delete()
                except Exception:
                    pass
            except asyncio.TimeoutError:
                # Benar-benar expired dan belum connected
                try:
                    await qr_message.delete()
                except Exception:
                    pass
                try:
                    await update.message.reply_text(
                        "QR code sudah expired. Ketik /qr untuk generate baru."
                    )
                except Exception:
                    pass

        asyncio.create_task(delete_after(qr_duration))

        # Poll status sampai connected atau timeout
        async def poll_connected(chat_id: int, dev_id: str, timeout_sec: int):
            deadline = asyncio.get_event_loop().time() + timeout_sec
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(3)
                try:
                    async with httpx.AsyncClient(auth=gowa_auth()) as cl:
                        r = await cl.get(
                            f"{GOWA_BASE_URL}/devices/{dev_id}/status", timeout=10
                        )
                    s = r.json().get("results", {})
                    if s.get("is_connected") and s.get("is_logged_in"):
                        connected_event.set()  # sinyal ke delete_after untuk hapus QR
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="WhatsApp berhasil terhubung! Bot siap menerima pesan."
                        )
                        return
                except Exception:
                    pass

        asyncio.create_task(
            poll_connected(update.effective_chat.id, device_id, qr_duration + 30)
        )

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        device_id = get_device_id()
        if not device_id:
            await update.message.reply_text(
                "Device belum dibuat. Gunakan /qr untuk membuat device dan login."
            )
            return

        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            status_resp = await client.get(
                f"{GOWA_BASE_URL}/devices/{device_id}/status", timeout=10
            )
            data = status_resp.json()

        result       = data.get("results", {})
        is_connected = result.get("is_connected", False)
        is_logged_in = result.get("is_logged_in", False)

        if is_connected and is_logged_in:
            await update.message.reply_text(
                "Status WhatsApp: TERHUBUNG\n\n"
                "WhatsApp sudah online dan siap menerima pesan."
            )
        elif is_logged_in and not is_connected:
            await update.message.reply_text(
                "Status WhatsApp: LOGIN tapi TERPUTUS\n\n"
                "Sudah login tapi koneksi terputus.\nGunakan /restart untuk reconnect."
            )
        else:
            await update.message.reply_text(
                "Status WhatsApp: TIDAK TERHUBUNG\n\n"
                "Gunakan /qr untuk login."
            )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        device_id = get_device_id()
        if not device_id:
            await update.message.reply_text("Device belum ada. Tidak ada yang perlu di-logout.")
            return

        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            resp = await client.post(
                f"{GOWA_BASE_URL}/devices/{device_id}/logout",
                timeout=10,
            )
            data = resp.json()
        await update.message.reply_text(
            f"Logout berhasil.\n{data.get('message', '')}\nGunakan /qr untuk login kembali."
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    try:
        device_id = get_device_id()
        if not device_id:
            await update.message.reply_text("Device belum ada. Gunakan /qr untuk membuat device.")
            return

        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            resp = await client.post(
                f"{GOWA_BASE_URL}/devices/{device_id}/reconnect",
                timeout=10,
            )
            data = resp.json()
        await update.message.reply_text(
            f"Reconnect berhasil.\n{data.get('message', '')}"
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text("Memuat ulang corpus dari Google Drive...")
    try:
        from services.corpus import load_corpus
        cfg = load_config()
        corpus_url = cfg.get("corpus_url", "")
        if not corpus_url:
            await update.message.reply_text(
                "Corpus URL belum dikonfigurasi. Selesaikan /setup terlebih dahulu."
            )
            return
        corpus_text = load_corpus(corpus_url)
        set_corpus = context.application.bot_data.get("set_corpus")
        if set_corpus:
            set_corpus(corpus_text)
        await update.message.reply_text(
            f"Corpus berhasil dimuat ulang.\n{len(corpus_text)} karakter dimuat."
        )
    except Exception as e:
        await update.message.reply_text(f"Gagal reload corpus: {e}")

async def _set_bot_commands(app):
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start",        "Tampilkan menu utama"),
        BotCommand("setup",        "Konfigurasi bot (brand, corpus, owner)"),
        BotCommand("qr",           "Login WhatsApp via QR code"),
        BotCommand("status",       "Cek status koneksi WhatsApp"),
        BotCommand("config",       "Lihat konfigurasi saat ini"),
        BotCommand("welcome",      "Edit pesan sambutan bot"),
        BotCommand("systemprompt", "Edit system prompt LLM"),
        BotCommand("reload",       "Reload corpus dari Google Drive"),
        BotCommand("restart",      "Restart koneksi WhatsApp"),
        BotCommand("logout",       "Logout session WhatsApp"),
    ])

def build_telegram_app():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_set_bot_commands)
        .build()
    )

    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", cmd_setup)],
        states={
            WAIT_BRAND_NAME:  [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_brand_name),
                CallbackQueryHandler(received_brand_name, pattern="^setup_"),
            ],
            WAIT_CORPUS_URL:  [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_corpus_url),
                CallbackQueryHandler(received_corpus_url, pattern="^setup_"),
            ],
            WAIT_OWNER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_owner_phone),
                CallbackQueryHandler(received_owner_phone, pattern="^setup_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_setup)],
        per_message=False,
        per_chat=True,
    )

    welcome_conv = ConversationHandler(
        entry_points=[CommandHandler("welcome", cmd_welcome)],
        states={
            WAIT_EDIT_WELCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_welcome_msg),
                CallbackQueryHandler(received_welcome_msg, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    systemprompt_conv = ConversationHandler(
        entry_points=[CommandHandler("systemprompt", cmd_systemprompt)],
        states={
            WAIT_EDIT_SYSTEMPROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_system_prompt),
                CallbackQueryHandler(received_system_prompt, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    app.add_handler(setup_conv)
    app.add_handler(welcome_conv)
    app.add_handler(systemprompt_conv)
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("config",  cmd_config))
    app.add_handler(CommandHandler("qr",      cmd_qr))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("logout",  cmd_logout))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("reload",  cmd_reload))
    return app
