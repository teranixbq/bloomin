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
TELEGRAM_ADMIN_IDS     = {
    int(x.strip())
    for x in os.getenv("TELEGRAM_ADMIN_USER_ID", "0").split(",")
    if x.strip()
}
GOWA_BASE_URL          = os.getenv("GOWA_BASE_URL", "http://gowa:3000")

GOWA_PUBLIC_URL = os.getenv("GOWA_PUBLIC_URL", "")
GOWA_BASIC_AUTH = os.getenv("GOWA_BASIC_AUTH", "")

def gowa_auth() -> httpx.BasicAuth | None:
    """Return BasicAuth untuk semua request ke GOWA, atau None jika tidak dikonfigurasi."""
    if not GOWA_BASIC_AUTH or ":" not in GOWA_BASIC_AUTH:
        return None
    user, passwd = GOWA_BASIC_AUTH.split(":", 1)
    return httpx.BasicAuth(user, passwd)

WAIT_KNOWLEDGE, WAIT_OWNER_PHONE, WAIT_BRAND_NAME = range(3)
WAIT_EDIT_WELCOME, WAIT_EDIT_SYSTEMPROMPT, WAIT_EDIT_KNOWLEDGE = range(3, 6)
WAIT_EDIT_BRAND, WAIT_EDIT_OWNERPHONE, WAIT_EDIT_WORKTIME = range(6, 9)

KNOWLEDGE_EXAMPLE = (
    "# JAM OPERASIONAL\n"
    "----------\n"
    "Senin - Jumat: 09.00 - 18.00\n"
    "Sabtu: 09.00 - 15.00\n"
    "Minggu & Hari Libur: Tutup\n\n"
    "# ALAMAT\n"
    "---------\n"
    "Jl. Contoh No. 123, Kota ABC\n\n"
    "# PRODUK / LAYANAN\n"
    "---------\n"
    "1. Produk A - Rp 50.000\n"
    "2. Produk B - Rp 75.000\n\n"
    "# KONTAK\n"
    "---------\n"
    "WhatsApp: 0812-3456-7890\n"
    "Instagram: @tokosaya\n"
    "Email: info@tokosaya.com"
)

def is_admin(update: Update) -> bool:
    return update.effective_user.id in TELEGRAM_ADMIN_IDS

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
            json={"name": "Bloomin-Admin"},
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
            "Selamat datang di Bloomin Bot Manager!\n\n"
            "Setup belum selesai. Ketik /setup untuk memulai konfigurasi."
        )
    else:
        await update.message.reply_text(
            "Bloomin Bot Manager\n\n"
            "Perintah tersedia:\n"
            "/setup - Setup wizard (step-by-step)\n"
            "/brand - Edit nama brand\n"
            "/knowledge - Edit knowledge\n"
            "/ownerphone - Edit nomor owner\n"
            "/worktime - Edit jam kerja\n"
            "/welcome - Edit pesan welcome\n"
            "/systemprompt - Edit system prompt\n"
            "/newlogin - Buat device baru & login\n"
            "/listdevice - Lihat semua device\n"
            "/switchdevice - Pindah device aktif\n"
            "/qr - Login WhatsApp via QR code\n"
            "/status - Cek status koneksi WhatsApp\n"
            "/config - Lihat konfigurasi saat ini\n"
            "/restart - Restart koneksi WhatsApp\n"
            "/logout - Logout WhatsApp"
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
    current_brand = cfg.get("brand_name", "Bloomin")
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
            brand_name = cfg.get("brand_name", "Bloomin")
            context.user_data["brand_name"] = brand_name
            current_chars = len(cfg.get("knowledge", ""))
            await query.edit_message_text(
                f"Brand dipertahankan: {brand_name}\n\n"
                "Langkah 2/3: Kirim *Knowledge* toko kamu — data/informasi yang dipakai bot "
                "untuk menjawab otomatis (jam operasional, alamat, harga, cara pesan, dll).\n\n"
                f"Nilai saat ini: {current_chars} karakter\n\n"
                "Contoh format:\n"
                f"{KNOWLEDGE_EXAMPLE}\n\n"
                "Kirim knowledge baru atau tekan Skip untuk mempertahankan.",
                reply_markup=_skip_cancel_keyboard(),
            )
            return WAIT_KNOWLEDGE

    brand_name = update.message.text.strip()
    if len(brand_name) < 2 or len(brand_name) > 50:
        await update.message.reply_text(
            "Nama brand tidak valid. Harus antara 2-50 karakter.\nCoba lagi:",
            reply_markup=_skip_cancel_keyboard(),
        )
        return WAIT_BRAND_NAME

    context.user_data["brand_name"] = brand_name
    cfg = load_config()
    current_chars = len(cfg.get("knowledge", ""))
    await update.message.reply_text(
        f"Nama brand: {brand_name}\n\n"
        "Langkah 2/3: Kirim *Knowledge* toko kamu — data/informasi yang dipakai bot "
        "untuk menjawab otomatis (jam operasional, alamat, harga, cara pesan, dll).\n\n"
        f"Nilai saat ini: {current_chars} karakter\n\n"
        "Contoh format:\n"
        f"{KNOWLEDGE_EXAMPLE}\n\n"
        "Kirim knowledge baru atau tekan Skip untuk mempertahankan.",
        reply_markup=_skip_cancel_keyboard(),
    )
    return WAIT_KNOWLEDGE

async def received_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            knowledge = cfg.get("knowledge", "")
            context.user_data["knowledge"] = knowledge
            current_phone = cfg.get("owner_phone", "-")
            await query.edit_message_text(
                f"Knowledge dipertahankan ({len(knowledge)} karakter).\n\n"
                "Langkah 3/3: Kirim nomor WhatsApp owner untuk menerima notifikasi.\n\n"
                f"Nilai saat ini: {current_phone}\n"
                "Kirim nomor baru atau tekan Skip untuk mempertahankan.",
                reply_markup=_skip_cancel_keyboard(),
            )
            return WAIT_OWNER_PHONE

    knowledge = update.message.text.strip()
    if len(knowledge) < 20:
        await update.message.reply_text(
            "Knowledge terlalu singkat (minimal 20 karakter). "
            "Isi informasi toko seperti jam operasional, alamat, harga, dll.\nCoba lagi:",
            reply_markup=_skip_cancel_keyboard(),
        )
        return WAIT_KNOWLEDGE

    context.user_data["knowledge"] = knowledge
    cfg = load_config()
    current_phone = cfg.get("owner_phone", "-")
    await update.message.reply_text(
        f"Knowledge tersimpan sementara ({len(knowledge)} karakter).\n\n"
        "Langkah 3/3: Kirim nomor WhatsApp owner untuk menerima notifikasi.\n\n"
        f"Nilai saat ini: {current_phone}\n"
        "Kirim nomor baru atau tekan Skip untuk mempertahankan.",
        reply_markup=_skip_cancel_keyboard(),
    )
    return WAIT_OWNER_PHONE

async def _finalize_setup(message, context, knowledge: str, brand_name: str, phone: str):
    cfg = load_config()
    cfg["knowledge"]     = knowledge
    cfg["owner_phone"]   = phone
    cfg["brand_name"]    = brand_name
    cfg["is_setup_done"] = True
    save_config(cfg)

    try:
        from services.llm import generate_welcome_msg
        set_knowledge = context.application.bot_data.get("set_knowledge")
        if set_knowledge:
            set_knowledge(knowledge)

        await message.reply_text("Generating pesan sambutan dari knowledge...")
        welcome_msg = await generate_welcome_msg(knowledge, brand_name)
        if welcome_msg:
            cfg = load_config()
            cfg["welcome_msg"] = welcome_msg
            save_config(cfg)

        await message.reply_text(
            f"Konfigurasi tersimpan!\n\n"
            f"Brand: {brand_name}\n"
            f"Nomor Owner: {phone}\n"
            f"Knowledge: {len(knowledge)} karakter\n\n"
            + (f"Pesan sambutan:\n{welcome_msg}\n\n" if welcome_msg else "Pesan sambutan menggunakan default.\n\n")
            + "Langkah selanjutnya: ketik /qr untuk login WhatsApp.\n"
              "Bot belum aktif sampai QR di-scan."
        )
    except Exception as e:
        await message.reply_text(
            f"Gagal memproses knowledge: {e}\n"
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
            knowledge  = context.user_data.get("knowledge", cfg.get("knowledge", ""))
            brand_name = context.user_data.get("brand_name", cfg.get("brand_name", "Bloomin"))
            await query.edit_message_text(f"Nomor owner dipertahankan: {phone}")
            await _finalize_setup(query.message, context, knowledge, brand_name, phone)
            return ConversationHandler.END

    phone = update.message.text.strip()
    if not phone.startswith("62") or not phone.isdigit():
        await update.message.reply_text(
            "Format nomor tidak valid. Harus diawali 62 dan hanya angka.\n"
            "Contoh: 628123456789\n\nCoba lagi:",
            reply_markup=_skip_cancel_keyboard(),
        )
        return WAIT_OWNER_PHONE

    knowledge  = context.user_data.get("knowledge", cfg.get("knowledge", ""))
    brand_name = context.user_data.get("brand_name", cfg.get("brand_name", "Bloomin"))
    await _finalize_setup(update.message, context, knowledge, brand_name, phone)
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
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Pesan Sambutan", callback_data="edit_welcome")]
    ])
    
    await update.message.reply_text(
        f"Pesan sambutan saat ini:\n\n{welcome_msg}",
        reply_markup=keyboard
    )

async def welcome_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Kirim pesan sambutan baru untuk mengubah.\n\n"
        "Ketik /cancel untuk membatalkan.",
        reply_markup=_cancel_keyboard()
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
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit System Prompt", callback_data="edit_systemprompt")]
    ])
    
    if len(msg) > 4000:
        await update.message.reply_text(msg[:4000])
        await update.message.reply_text(
            msg[4000:],
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            msg,
            reply_markup=keyboard
        )

async def systemprompt_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Kirim system prompt baru untuk mengubah.\n\n"
        "Ketik /cancel untuk membatalkan.",
        reply_markup=_cancel_keyboard()
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

async def cmd_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    brand_name = cfg.get("brand_name", "Bloomin")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Brand", callback_data="edit_brand")]
    ])
    
    await update.message.reply_text(
        f"Brand saat ini: {brand_name}",
        reply_markup=keyboard
    )

async def brand_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Kirim nama brand baru untuk mengubah.\n\n"
        "Tekan tombol Cancel untuk membatalkan.",
        reply_markup=_cancel_keyboard()
    )
    return WAIT_EDIT_BRAND

async def received_brand_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Dibatalkan.")
        return ConversationHandler.END
    
    new_brand = update.message.text.strip()
    if len(new_brand) < 2:
        await update.message.reply_text(
            "Nama brand terlalu pendek (minimal 2 karakter). Coba lagi.",
            reply_markup=_cancel_keyboard()
        )
        return WAIT_EDIT_BRAND
    
    cfg = load_config()
    cfg["brand_name"] = new_brand
    save_config(cfg)
    
    await update.message.reply_text(
        f"✅ Brand berhasil diperbarui menjadi: {new_brand}"
    )
    return ConversationHandler.END

async def cmd_ownerphone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    owner_phone = cfg.get("owner_phone", "-")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Nomor Owner", callback_data="edit_ownerphone")]
    ])
    
    await update.message.reply_text(
        f"Nomor owner saat ini: {owner_phone}",
        reply_markup=keyboard
    )

async def ownerphone_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Kirim nomor owner baru (format: 62xxxxxxxxxx) untuk mengubah.\n\n"
        "Tekan tombol Cancel untuk membatalkan.",
        reply_markup=_cancel_keyboard()
    )
    return WAIT_EDIT_OWNERPHONE

async def received_ownerphone_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima nomor owner baru dari edit mode"""
    if not is_admin(update):
        return ConversationHandler.END
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Dibatalkan.")
        return ConversationHandler.END
    
    owner_phone = update.message.text.strip()
    if not owner_phone.startswith("62") or not owner_phone.isdigit():
        await update.message.reply_text(
            "⚠️ Format nomor tidak valid. Harus diawali 62 dan hanya angka.\n"
            "Contoh: 6281234567890\n\nCoba lagi:",
            reply_markup=_cancel_keyboard()
        )
        return WAIT_EDIT_OWNERPHONE
    
    cfg = load_config()
    cfg["owner_phone"] = owner_phone
    save_config(cfg)
    
    await update.message.reply_text(
        f"✅ Nomor owner berhasil diperbarui: {owner_phone}"
    )
    return ConversationHandler.END

async def cmd_worktime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command untuk melihat dan mengedit jam kerja"""
    if not is_admin(update):
        return
    cfg = load_config()
    work_time = cfg.get("work_time", {"open": "08:00", "close": "17:00"})
    
    open_time = work_time.get("open", "08:00")
    close_time = work_time.get("close", "17:00")
    
    msg = (
        f"*Jam Kerja*\n\n"
        f"Jam Buka: {open_time}\n"
        f"Jam Tutup: {close_time}\n\n"
        f"Bot akan membalas pesan di luar jam kerja dengan informasi bahwa pesan akan dibalas besok."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Jam", callback_data="edit_worktime")]
    ])
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def worktime_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle klik tombol Edit Jam Kerja"""
    if not is_admin(update):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    cfg = load_config()
    work_time = cfg.get("work_time", {"enabled": False, "open": "08:00", "close": "17:00"})
    
    await query.edit_message_text(
        f"*Edit Jam Kerja*\n\n"
        f"Kirim format: `jam_buka,jam_tutup`\n\n"
        f"Contoh:\n"
        f"`08:00,17:00`\n\n"
        f"Nilai saat ini:\n"
        f"`{work_time.get('open', '08:00')},{work_time.get('close', '17:00')}`\n\n"
        f"Tekan tombol Cancel untuk membatalkan.",
        parse_mode="Markdown",
        reply_markup=_cancel_keyboard()
    )
    return WAIT_EDIT_WORKTIME

async def received_worktime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima pengaturan jam kerja baru dari edit mode"""
    if not is_admin(update):
        return ConversationHandler.END
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Dibatalkan.")
        return ConversationHandler.END
    
    worktime_text = update.message.text.strip()
    
    # Parse format: open,close
    try:
        parts = worktime_text.split(",")
        if len(parts) != 2:
            raise ValueError("Format harus: jam_buka,jam_tutup")
        
        open_time = parts[0].strip()
        close_time = parts[1].strip()
        
        # Validasi format waktu
        import re
        if not re.match(r"^\d{2}:\d{2}$", open_time) or not re.match(r"^\d{2}:\d{2}$", close_time):
            raise ValueError("Format waktu harus HH:MM")
        
        cfg = load_config()
        work_time = cfg.get("work_time", {"enabled": False})
        work_time["open"] = open_time
        work_time["close"] = close_time
        cfg["work_time"] = work_time
        save_config(cfg)
        
        enabled_status = "🟢 Aktif" if work_time.get("enabled", False) else "🔴 Tidak Aktif"
        await update.message.reply_text(
            f"✅ Jam kerja berhasil diperbarui!\n\n"
            f"Status: {enabled_status}\n"
            f"Jam Buka: {open_time}\n"
            f"Jam Tutup: {close_time}"
        )
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Format tidak valid: {str(e)}\n\n"
            f"Gunakan format: `jam_buka,jam_tutup`\n"
            f"Contoh: `08:00,17:00`\n\n"
            f"Coba lagi:",
            parse_mode="Markdown",
            reply_markup=_cancel_keyboard()
        )
        return WAIT_EDIT_WORKTIME
        return WAIT_EDIT_WORKTIME

async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    knowledge_text = cfg.get("knowledge", "")
    
    await update.message.reply_text(
        f"Konfigurasi saat ini:\n\n"
        f"Setup selesai: {'Ya' if cfg.get('is_setup_done') else 'Belum'}\n"
        f"Knowledge: {len(knowledge_text)} karakter (lihat /knowledge)\n"
        f"Nomor Owner: {cfg.get('owner_phone', '-')}\n"
        f"Device ID: {cfg.get('device_id') or '-'}\n\n"
        "Ketik /setup untuk mengubah konfigurasi."
    )

async def cmd_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    cfg = load_config()
    knowledge_text = cfg.get("knowledge", "")
    
    if knowledge_text:
        # Tampilkan isi knowledge dengan tombol Edit
        msg = f"Knowledge saat ini ({len(knowledge_text)} karakter):\n\n```\n{knowledge_text}\n```"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Edit Knowledge", callback_data="edit_knowledge")]
        ])
        
        # Telegram limit 4096 chars
        if len(msg) > 4000:
            await update.message.reply_text(
                msg[:4000] + "\n\n... (terpotong)",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                msg,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    else:
        await update.message.reply_text(
            "Knowledge belum diatur.\n\n"
            "Ketik /setup untuk menambahkan knowledge."
        )

async def knowledge_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle klik tombol Edit Knowledge"""
    if not is_admin(update):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Kirimkan knowledge baru (teks bebas):\n\n"
        f"Contoh format:\n```\n{KNOWLEDGE_EXAMPLE}\n```\n\n"
        "Tekan tombol Cancel untuk membatalkan.",
        parse_mode="Markdown",
        reply_markup=_cancel_keyboard()
    )
    return WAIT_EDIT_KNOWLEDGE

async def received_knowledge_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima knowledge baru dari edit mode"""
    if not is_admin(update):
        return ConversationHandler.END
    
    # Handle tombol Cancel
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Dibatalkan.")
        return ConversationHandler.END
    
    knowledge_text = update.message.text.strip()
    
    if len(knowledge_text) < 20:
        await update.message.reply_text(
            "⚠️ Knowledge terlalu pendek (minimal 20 karakter). Coba lagi.",
            reply_markup=_cancel_keyboard()
        )
        return WAIT_EDIT_KNOWLEDGE
    
    cfg = load_config()
    brand_name = cfg.get("brand_name", "Bloomin")
    cfg["knowledge"] = knowledge_text
    save_config(cfg)
    
    # Update knowledge di runtime
    set_knowledge = context.bot_data.get("set_knowledge")
    if set_knowledge:
        set_knowledge(knowledge_text)
    
    # Generate ulang welcome message dari knowledge baru
    await update.message.reply_text("✅ Knowledge berhasil diperbarui.\n\n⏳ Generating pesan sambutan baru...")
    
    from services.llm import generate_welcome_msg
    welcome_msg = await generate_welcome_msg(knowledge_text, brand_name)
    
    if welcome_msg:
        cfg = load_config()
        cfg["welcome_msg"] = welcome_msg
        save_config(cfg)
        
        await update.message.reply_text(
            f"✅ Knowledge berhasil diperbarui ({len(knowledge_text)} karakter).\n\n"
            f"Pesan sambutan baru:\n{welcome_msg}\n\n"
            "Ketik /knowledge untuk melihat atau edit ulang."
        )
    else:
        await update.message.reply_text(
            f"✅ Knowledge berhasil diperbarui ({len(knowledge_text)} karakter).\n\n"
            "⚠️ Gagal generate pesan sambutan baru. Menggunakan pesan sambutan sebelumnya.\n\n"
            "Ketik /knowledge untuk melihat atau edit ulang."
        )
    
    return ConversationHandler.END

async def cmd_newlogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buat device baru dan langsung show QR untuk login"""
    if not is_admin(update):
        return
    
    await update.message.reply_text("Membuat device baru...")
    
    try:
        # Buat device baru di GOWA
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            resp = await client.post(f"{GOWA_BASE_URL}/devices", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
        device_id = data.get("device_id")
        if not device_id:
            await update.message.reply_text("❌ Gagal membuat device baru")
            return
            
        await update.message.reply_text(
            f"✅ Device baru dibuat!\n"
            f"Device ID: {device_id}\n\n"
            "Mengambil QR code untuk login..."
        )
        
        # Ambil QR code
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            qr_resp = await client.get(f"{GOWA_BASE_URL}/devices/{device_id}/qr", timeout=15)
            qr_resp.raise_for_status()
            qr_data = qr_resp.json()
            
        qr_code = qr_data.get("qr")
        if not qr_code:
            await update.message.reply_text("❌ Gagal mengambil QR code")
            return
            
        # Kirim QR code sebagai foto
        qr_message = await update.message.reply_photo(
            photo=qr_code,
            caption=(
                f"📱 Scan QR ini dengan WhatsApp:\n\n"
                f"1. Buka WhatsApp\n"
                f"2. Tap ⋮ (menu) > Linked Devices\n"
                f"3. Tap 'Link a Device'\n"
                f"4. Scan QR di atas\n\n"
                f"⏱️ QR berlaku 60 detik\n"
                f"Device ID: `{device_id}`"
            ),
            parse_mode="Markdown"
        )
        
        # Poll status sampai connected atau timeout
        start_time = asyncio.get_event_loop().time()
        timeout = 60
        poll_interval = 2
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(poll_interval)
            
            try:
                async with httpx.AsyncClient(auth=gowa_auth()) as client:
                    status_resp = await client.get(f"{GOWA_BASE_URL}/devices/{device_id}/status", timeout=10)
                    status_data = status_resp.json()
                    
                status = status_data.get("status")
                
                if status == "connected":
                    # Delete QR message
                    try:
                        await qr_message.delete()
                    except:
                        pass
                    
                    # Update config dengan device baru
                    cfg = load_config()
                    old_device = cfg.get("device_id", "Tidak ada")
                    cfg["device_id"] = device_id
                    save_config(cfg)
                    
                    await update.message.reply_text(
                        f"✅ WhatsApp berhasil terhubung!\n\n"
                        f"📱 Device ID: `{device_id}`\n"
                        f"🔄 Bot sekarang menggunakan device ini\n\n"
                        f"Device lama (`{old_device}`) masih tersimpan tapi tidak aktif.\n\n"
                        f"Gunakan /listdevice untuk melihat semua device\n"
                        f"Gunakan /switchdevice untuk berpindah device",
                        parse_mode="Markdown"
                    )
                    return
                    
            except Exception as e:
                print(f"Error polling status: {e}")
                continue
                
        # Timeout
        await update.message.reply_text(
            "⏱️ Timeout! QR code sudah expired.\n\n"
            f"Device ID `{device_id}` sudah dibuat tapi belum login.\n"
            f"Gunakan /login untuk login ke device ini.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cmd_listdevice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List semua device dengan tombol delete"""
    if not is_admin(update):
        return
        
    try:
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            resp = await client.get(f"{GOWA_BASE_URL}/devices", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
        devices = data.get("results", [])
        
        if not devices:
            await update.message.reply_text("📱 Tidak ada device terdaftar")
            return
            
        cfg = load_config()
        active_device = cfg.get("device_id")
        
        message = "📱 *Daftar Device WhatsApp*\n\n"
        keyboard = []
        
        for idx, device in enumerate(devices, 1):
            device_id = device.get("id")
            state = device.get("state", "unknown")
            
            # State emoji
            state_emoji = "🟢" if state == "logged_in" else "🔴"
            active_emoji = "⭐ " if device_id == active_device else ""
            
            message += f"{idx}. {active_emoji}{state_emoji} `{device_id[:8]}...`\n"
            
            # Tombol delete (tidak bisa delete active device)
            if device_id != active_device:
                keyboard.append([InlineKeyboardButton(
                    f"🗑️ Delete #{idx}",
                    callback_data=f"delete_device:{device_id}"
                )])
                
        if not keyboard:
            message += "\nℹ️ Tidak ada device yang bisa dihapus (device aktif tidak bisa dihapus)"
            
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def delete_device_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle delete device button"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update):
        return
        
    device_id = query.data.split(":")[1]
    
    try:
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            resp = await client.delete(f"{GOWA_BASE_URL}/devices/{device_id}", timeout=10)
            resp.raise_for_status()
            
        await query.edit_message_text(
            f"✅ Device `{device_id[:8]}...` berhasil dihapus",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Gagal menghapus device: {str(e)}")


async def cmd_switchdevice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch ke device lain"""
    if not is_admin(update):
        return
        
    try:
        async with httpx.AsyncClient(auth=gowa_auth()) as client:
            resp = await client.get(f"{GOWA_BASE_URL}/devices", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
        devices = data.get("results", [])
        cfg = load_config()
        active_device = cfg.get("device_id")
        
        # Filter hanya device yang logged_in
        connected_devices = [d for d in devices if d.get("state") == "logged_in"]
        
        if len(connected_devices) <= 1:
            await update.message.reply_text(
                "📱 Hanya ada 1 device yang terhubung (atau tidak ada).\n\n"
                "Gunakan /newlogin untuk menambah device baru."
            )
            return
            
        message = "🔄 *Pilih Device untuk Diaktifkan*\n\n"
        keyboard = []
        
        for device in connected_devices:
            device_id = device.get("id")
            is_active = "⭐ (AKTIF)" if device_id == active_device else ""
            
            keyboard.append([InlineKeyboardButton(
                f"📱 {device_id[:8]}... {is_active}",
                callback_data=f"switch_device:{device_id}"
            )])
            
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def switch_device_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle switch device button"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update):
        return
        
    device_id = query.data.split(":")[1]
    
    try:
        cfg = load_config()
        cfg["device_id"] = device_id
        save_config(cfg)
        
        await query.edit_message_text(
            f"✅ Berhasil switch ke device `{device_id[:8]}...`\n\n"
            f"Bot sekarang menggunakan device ini untuk menerima pesan.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")


# State untuk worktime edit
WAIT_EDIT_WORKTIME = range(1)

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

async def _set_bot_commands(app):
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start",        "Tampilkan menu utama"),
        BotCommand("setup",        "Setup wizard (step-by-step)"),
        BotCommand("brand",        "Edit nama brand"),
        BotCommand("knowledge",    "Edit knowledge"),
        BotCommand("ownerphone",   "Edit nomor owner"),
        BotCommand("worktime",     "Edit jam kerja"),
        BotCommand("welcome",      "Edit pesan welcome"),
        BotCommand("systemprompt", "Edit system prompt"),
        BotCommand("qr",           "Login WhatsApp via QR code"),
        BotCommand("status",       "Cek status koneksi WhatsApp"),
        BotCommand("config",       "Lihat konfigurasi saat ini"),
        BotCommand("restart",      "Restart koneksi WhatsApp"),
        BotCommand("logout",       "Logout WhatsApp"),
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
            WAIT_KNOWLEDGE:  [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_knowledge),
                CallbackQueryHandler(received_knowledge, pattern="^setup_"),
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
        entry_points=[
            CommandHandler("welcome", cmd_welcome),
            CallbackQueryHandler(welcome_edit_callback, pattern="^edit_welcome$")
        ],
        states={
            WAIT_EDIT_WELCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_welcome_msg),
                CallbackQueryHandler(cancel_edit, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    systemprompt_conv = ConversationHandler(
        entry_points=[
            CommandHandler("systemprompt", cmd_systemprompt),
            CallbackQueryHandler(systemprompt_edit_callback, pattern="^edit_systemprompt$")
        ],
        states={
            WAIT_EDIT_SYSTEMPROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_system_prompt),
                CallbackQueryHandler(cancel_edit, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    knowledge_conv = ConversationHandler(
        entry_points=[
            CommandHandler("knowledge", cmd_knowledge),
            CallbackQueryHandler(knowledge_edit_callback, pattern="^edit_knowledge$"),
        ],
        states={
            WAIT_EDIT_KNOWLEDGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_knowledge_edit),
                CallbackQueryHandler(cancel_edit, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    brand_conv = ConversationHandler(
        entry_points=[
            CommandHandler("brand", cmd_brand),
            CallbackQueryHandler(brand_edit_callback, pattern="^edit_brand$"),
        ],
        states={
            WAIT_EDIT_BRAND: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_brand_edit),
                CallbackQueryHandler(cancel_edit, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    ownerphone_conv = ConversationHandler(
        entry_points=[
            CommandHandler("ownerphone", cmd_ownerphone),
            CallbackQueryHandler(ownerphone_edit_callback, pattern="^edit_ownerphone$"),
        ],
        states={
            WAIT_EDIT_OWNERPHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_ownerphone_edit),
                CallbackQueryHandler(cancel_edit, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    worktime_conv = ConversationHandler(
        entry_points=[
            CommandHandler("worktime", cmd_worktime),
            CallbackQueryHandler(worktime_edit_callback, pattern="^edit_worktime$"),
        ],
        states={
            WAIT_EDIT_WORKTIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_worktime),
                CallbackQueryHandler(cancel_edit, pattern="^edit_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
    )

    app.add_handler(setup_conv)
    app.add_handler(welcome_conv)
    app.add_handler(systemprompt_conv)
    app.add_handler(knowledge_conv)
    app.add_handler(brand_conv)
    app.add_handler(ownerphone_conv)
    app.add_handler(worktime_conv)
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("config",  cmd_config))
    app.add_handler(CommandHandler("qr",      cmd_qr))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("logout",  cmd_logout))
    app.add_handler(CommandHandler("restart", cmd_restart))
    
    # Multi-device handlers
    app.add_handler(CommandHandler("newlogin", cmd_newlogin))
    app.add_handler(CommandHandler("listdevice", cmd_listdevice))
    app.add_handler(CommandHandler("switchdevice", cmd_switchdevice))
    app.add_handler(CallbackQueryHandler(delete_device_callback, pattern="^delete_device:"))
    app.add_handler(CallbackQueryHandler(switch_device_callback, pattern="^switch_device:"))
    
    return app
