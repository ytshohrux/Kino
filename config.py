import os


def _require(name: str) -> str:
    """Muhim qiymat environment'da bo'lmasa, bot ishga tushmasdan xato beradi."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"'{name}' environment variable o'rnatilmagan!")
    return value


# Barchasi Render > Environment bo'limida kiritiladi (kodda yozilmaydi)
BOT_TOKEN = _require("BOT_TOKEN")
MONGO_URI = _require("MONGO_URI")
WEBHOOK_URL = _require("WEBHOOK_URL")
SUPER_ADMIN_ID = int(_require("SUPER_ADMIN_ID"))

# Render portni o'zi beradi
PORT = int(os.getenv("PORT", 8000))
