# Semua pesan, keywords, dan timeout values bot WhatsApp

# Timeout session (detik)
SESSION_INACTIVITY    = 300   # tanya "masih di sini?" (5 menit)
SESSION_CLOSE_WAIT    = 120   # tutup sesi setelah ping
SESSION_OWNER_TIMEOUT = 300   # tutup sesi owner (5 menit)

# Pesan bot WhatsApp
MSG_WELCOME_DEFAULT = (
    "Halo kak! Selamat datang di *Bloomin* 🌸\n"
    "Ada yang bisa kami bantu hari ini?\n\n"
    "Kamu bisa tanya tentang:\n"
    "• Katalog & harga bunga\n"
    "• Cara pemesanan\n"
    "• Info pengiriman\n"
    "• Dan lainnya seputar toko kami\n\n"
    "Ketik /admin kalau ingin langsung bicara dengan admin kami 😊"
)

MSG_STILL_THERE = "Hai kak, masih di sini? 😊 Ada lagi yang bisa kami bantu?"

MSG_CLOSING = (
    "Terima kasih sudah menghubungi kami 🌸\n"
    "Semoga harimu menyenangkan! Jangan sungkan untuk chat lagi ya kak 😊"
)

MSG_TIMEOUT_CLOSE = (
    "Sepertinya kakak sudah tidak ada di sini 😊\n"
    "Sesi chat sudah kami tutup. Sampai jumpa lagi dan selamat beraktivitas! 🌸"
)

MSG_OWNER_WAITING = (
    "Baik kak, kami sudah menghubungi penjual kami 🌸\n"
    "Mohon tunggu sebentar, penjual akan segera menghubungi kakak langsung ya 😊"
)

MSG_OWNER_TIMEOUT = (
    "Mohon maaf, admin sedang tidak bisa dihubungi saat ini 🙏\n"
    "Silakan hubungi kami lagi beberapa saat lagi ya."
)

MSG_BOT_REJECT = (
    "Maaf kak, saya hanya bisa bantu seputar toko bunga kami 🌸\n"
    "Untuk pertanyaan lain, silakan hubungi admin kami langsung dengan mengetik /admin"
)

MSG_LLM_ERROR = (
    "Maaf kak, bot kami sedang dalam perbaikan saat ini 🙏\n"
    "Silakan hubungi admin kami langsung dengan mengetik /admin\n\n"
    "Terima kasih sudah menghubungi kami 🌸"
)

MSG_FORWARD_TO_OWNER = (
    "Pertanyaan kakak sudah kami teruskan ke admin kami ya 🌸\n"
    "Mohon tunggu sebentar, admin kami akan segera membalas."
)

MSG_TIDAK_TAHU = (
    "Maaf kak, informasi tersebut belum ada di data kami saat ini 🙏\n\n"
    "Apakah kakak ingin kami hubungkan ke penjual kami langsung?\n"
    "Balas *ya* atau *tidak* ya kak 😊"
)

MSG_ADMIN_CONFIRM = (
    "Apakah kakak ingin dihubungkan ke penjual kami langsung? 🌸\n"
    "Balas *ya* atau *tidak* ya kak 😊"
)

MSG_ADMIN_CONFIRM_NO = "Oke kak, tidak masalah 😊 Ada lagi yang bisa saya bantu?"

MSG_ADMIN_CONFIRM_UNCLEAR = (
    "Maaf kak, saya kurang mengerti 😊\n"
    "Apakah kakak ingin dihubungkan ke penjual kami? Balas *ya* atau *tidak* ya kak."
)

MSG_ACTIVE_SESSION_GREETING = "Ada lagi yang bisa dibantu kak? 😊"

MSG_NOT_READY = "Maaf, bot sedang dalam proses konfigurasi. Silakan coba beberapa saat lagi 🌸"

MSG_ADMIN_FORWARDED = (
    "Permintaan kamu sudah kami teruskan ke admin kami ya 🌸\n"
    "Mohon tunggu sebentar, admin kami akan segera menghubungi kamu."
)

# Template notif ke WA owner — format dengan .format(sender_phone=..., question=...)
MSG_OWNER_NOTIF = (
    "🌸 *Ada pelanggan minta dihubungi!*\n\n"
    "📱 Nomor: {sender_phone}\n"
    "💬 Pesan: \"{question}\"\n\n"
    "Silakan balas langsung ke nomor tersebut ya."
)

# Keywords deteksi intent user
CLOSING_KEYWORDS = {
    "terima kasih", "terimakasih", "makasih", "makasi", "thanks", "thank you",
    "bye", "goodbye", "dadah", "sampai jumpa", "ok makasih",
    "oke makasih", "oke terima kasih", "ok terima kasih", "selesai", "done",
    "udah cukup", "sudah cukup", "cukup", "gak perlu", "ngga perlu", "ga perlu",
}

ADMIN_KEYWORDS = {
    "hubungi", "hubungkan", "admin", "penjual", "cs", "customer service",
    "operator", "manusia", "orang", "staf", "staff", "langsung",
    "bicara", "ngobrol", "kontak", "contact", "tanya langsung",
    "mau pesan", "mau order", "mau beli", "pesan langsung", "order langsung",
}

YES_KEYWORDS = {"ya", "yes", "yep", "yap", "iya", "ok", "oke", "okay", "betul", "benar", "yoi", "y"}
NO_KEYWORDS  = {"tidak", "tidak mau", "gak", "ngga", "nggak", "no", "batal", "cancel", "jangan", "n"}

GREETINGS_REPLY = {
    "halo", "hai", "hi", "hello", "hei", "hey",
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    "pagi", "siang", "sore", "malam", "assalamualaikum", "permisi",
}

# Default system prompt — disimpan di config.json setelah setup, bisa diedit via /systemprompt
DEFAULT_SYSTEM_PROMPT = (
    "Kamu adalah asisten virtual toko bunga {brand_name} yang ramah dan helpful.\n"
    "Tugasmu adalah menjawab pertanyaan pelanggan berdasarkan informasi toko yang diberikan.\n\n"
    "Aturan penting:\n"
    "- Jawab HANYA berdasarkan informasi yang ada di konteks\n"
    "- Jawab singkat, natural, dan ramah dalam bahasa Indonesia\n"
    "- Kalau pertanyaan tidak ada di konteks, balas persis: TIDAK_TAHU\n"
    "- Jangan mengarang informasi yang tidak ada\n"
    "- JANGAN pernah mulai jawaban dengan salam seperti \"Halo!\", \"Hi kak!\", \"Selamat datang!\" — langsung jawab pertanyaannya saja\n\n"
    "Format untuk WhatsApp (WAJIB diikuti):\n"
    "- Gunakan *teks* untuk judul atau nama produk (bold di WhatsApp)\n"
    "- Untuk daftar/list gunakan • (bullet) diikuti spasi\n"
    "- Jangan gunakan # atau ** (tidak didukung WhatsApp)\n"
    "- Boleh gunakan emoji secukupnya agar ramah\n"
    "- Pisahkan setiap item dengan baris baru\n\n"
    "Informasi toko:\n{knowledge}"
)
