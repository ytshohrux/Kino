import os

# Telegram bot tokeni (@BotFather dan olinadi)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8450474807:AAE79-IJyX8EvWHjZl4qGJdL3HC1lYY-CRg")

# MongoDB ulanish havolasi (URI)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://famonov054_db_user:m17VCDTkYQkcLcX@kino.2zcd5fu.mongodb.net/?appName=Kino")

# Webhook manzili (Render.com dagi ilova havolasi: masalan https://kino-bot.onrender.com/webhook)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://kino-pa22.onrender.com/webhook")

# Asosiy admin (Super Admin) ning Telegram ID si
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "7162630033"))

# Render.com porti
PORT = int(os.getenv("PORT", 8000))
