import os

# Telegram bot tokeni (@BotFather dan olinadi)
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")

# MongoDB ulanish havolasi (URI)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://user:password@cluster.mongodb.net/?retryWrites=true&w=majority")

# Webhook manzili (Render.com dagi ilova havolasi: masalan https://kino-bot.onrender.com/webhook)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://kino-bot.onrender.com/webhook")

# Asosiy admin (Super Admin) ning Telegram ID si
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "123456789"))

# Render.com porti
PORT = int(os.getenv("PORT", 8000))
