import os
import json
import asyncio
import time
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from database import Database as db
import config

# Bot va FastAPI
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = FastAPI()

# Asosiy pastki tugmalar menyusi
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Kino qidirish")],
        [KeyboardButton(text="🏆 Top kinolar"), KeyboardButton(text="👥 Takliflarim")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="✍️ Adminga yozish")]
    ],
    resize_keyboard=True
)

ADMIN_BTN = "👨‍💻 Admin panel"

async def menu_for(user_id: int) -> ReplyKeyboardMarkup:
    """Oddiy foydalanuvchiga main_menu, adminga esa qo'shimcha Admin panel tugmasi bilan."""
    if await db.is_admin(user_id):
        return ReplyKeyboardMarkup(
            keyboard=main_menu.keyboard + [[KeyboardButton(text=ADMIN_BTN)]],
            resize_keyboard=True
        )
    return main_menu

# Cache uchun o'zgaruvchilar (Smart Channels)
channels_cache = {"data": [], "last_updated": 0}

async def get_cached_channels():
    current_time = time.time()
    if current_time - channels_cache["last_updated"] > 60:
        channels_cache["data"] = await db.get_channels()
