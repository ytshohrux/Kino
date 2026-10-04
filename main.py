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
        channels_cache["last_updated"] = current_time
    return channels_cache["data"]

async def check_channel_limits():
    all_channels = await get_cached_channels()
    for ch in all_channels:
        if ch["is_required"] and ch["target_subs"] > 0:
            try:
                count = await bot.get_chat_member_count(ch["channel_id"])
                if count >= ch["target_subs"]:
                    await db.update_channel_status(ch["channel_id"], False)
                    channels_cache["last_updated"] = 0 
                    try:
                        await bot.send_message(
                            config.SUPER_ADMIN_ID,
                            f"🔔 <b>{ch['title']}</b> kanali majburiy obuna limitiga ({ch['target_subs']}) yetdi va ixtiyoriy (homiy) kanalga o'tkazildi."
                        )
                    except: pass
            except Exception as e:
                print(f"Kanalni tekshirishda xatolik: {e}")

async def is_subscribed(user_id: int) -> tuple[bool, InlineKeyboardMarkup]:
    await check_channel_limits()
    all_channels = await get_cached_channels()
    
    keyboard = []
    is_subbed = True
    
    for ch in all_channels:
        if ch["is_required"]:
            try:
                member = await bot.get_chat_member(ch["channel_id"], user_id)
                if member.status in ['left', 'kicked']:
                    is_subbed = False
            except:
                is_subbed = False
        
        keyboard.append([InlineKeyboardButton(text=ch["title"], url=ch["url"])])
        
    return is_subbed, InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    ref_user_id = None
    admin_ref = None

    if args:
        if args.isdigit():
            movie_test = await db.get_movie(args)
            if not movie_test: 
                ref_user_id = int(args)
        else:
            admin_ref = args

    is_new = await db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username, ref_user_id, admin_ref)
    
    if is_new:
        if ref_user_id:
            try:
                await bot.send_message(ref_user_id, "🥳 Sizning taklif havolangiz orqali yangi foydalanuvchi qo'shildi!")
            except: pass
        if admin_ref:
            await db.add_admin_ref(admin_ref)

    subbed, markup = await is_subscribed(message.from_user.id)
    if not subbed:
        markup.inline_keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data=f"check_{args if args else 'none'}")])
        await message.answer("⚠️ <b>Botdan to'liq foydalanish va kinolarni ko'rish uchun quyidagi kanallarga obuna bo'ling:</b>", reply_markup=markup)
        return

    if args and await db.get_movie(args):
        await send_movie(message, args)
    else:
        await message.answer("🎬 <b>Xush kelibsiz! Kino izlash uchun kino kodini yoki nomini yuboring yoki pastdagi tugmalardan foydalaning:</b>", reply_markup=await menu_for(message.from_user.id))

@dp.callback_query(F.data.startswith("check_"))
async def check_sub_callback(call: types.CallbackQuery):
    args = call.data.split("_")[1]
    args = None if args == "none" else args

    subbed, markup = await is_subscribed(call.from_user.id)
    if not subbed:
        markup.inline_keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data=call.data)])
        await call.answer("Barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        await call.message.edit_text("⚠ <b>Botdan to'liq foydalanish va kinolarni ko'rish uchun quyidagi kanallarga obuna bo'ling:</b>", reply_markup=markup)
        return

    await call.message.delete()
    if args and await db.get_movie(args):
        await send_movie(call.message, args, call.from_user.id)
    else:
        await bot.send_message(call.from_user.id, "🎬 <b>Xush kelibsiz! Kino kodini yoki nomini yuboring:</b>", reply_markup=await menu_for(call.from_user.id))

async def send_movie(message_or_call, movie_code: str, chat_id: int = None):
    target_chat = chat_id if chat_id else message_or_call.chat.id
    movie = await db.get_movie(movie_code)
    if movie:
        await bot.send_video(target_chat, video=movie["file_id"], caption=f"🍿 <b>{movie['title']}</b>\n\n@{(await bot.get_me()).username} orqali topildi!", reply_markup=await menu_for(target_chat))
    else:
        await bot.send_message(target_chat, "❌ Bunday kino topilmadi.", reply_markup=await menu_for(target_chat))

# Pastki tugmalar uchun handlerlar
@dp.message(F.text == "🎬 Kino qidirish")
async def btn_search_movie(message: types.Message):
    await message.answer("🔍 <b>Kino kodini yoki nomini yuboring:</b>", reply_markup=await menu_for(message.from_user.id))

@dp.message(F.text == "👥 Takliflarim")
async def btn_my_refs(message: types.Message):
    count = await db.get_user_refs_count(message.from_user.id)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"👥 <b>Sizning takliflaringiz:</b> {count} ta\n🔗 <b>Maxsus havolangiz:</b> {link}", reply_markup=await menu_for(message.from_user.id))

@dp.message(F.text == "📊 Statistika")
async def btn_stats(message: types.Message):
    tot, act, blk = await db.get_stats()
    await message.answer(f"📊 <b>Bot Statistikasi:</b>\n\n👥 Jami foydalanuvchilar: {tot}\n✅ Faol: {act}\n❌ Bloklaganlar: {blk}", reply_markup=await menu_for(message.from_user.id))

@dp.message(F.text == "✍️ Adminga yozish")
async def btn_support(message: types.Message):
    await message.answer("📞 Savollar va takliflar uchun adminga murojaat qiling: @Shohruh_Sulaymonov", reply_markup=await menu_for(message.from_user.id))

@dp.message(F.text == "🏆 Top kinolar")
async def btn_top_movies(message: types.Message):
    await message.answer("🏆 Tez kunda eng ko'p ko'rilgan kinolar ro'yxati qo'shiladi!", reply_markup=await menu_for(message.from_user.id))


# ---------------- ADMIN PANEL ----------------
def admin_inline_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats"),
         InlineKeyboardButton(text="📢 Kanallar", callback_data="adm_channels")],
        [InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="adm_add"),
         InlineKeyboardButton(text="📝 Post yaratish", callback_data="adm_post")],
        [InlineKeyboardButton(text="📨 Xabar tarqatish", callback_data="adm_broadcast"),
         InlineKeyboardButton(text="📣 Reklama referallari", callback_data="adm_refs")],
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="adm_addch")],
    ])

ADMIN_TEXT = "<b>👨‍💻 Admin panelga xush kelibsiz!</b>\n\nKerakli bo'limni tanlang:"

@dp.message(F.text == ADMIN_BTN)
async def btn_admin_panel(message: types.Message):
    if not await db.is_admin(message.from_user.id):
        return await message.answer("❌ Siz admin emassiz!")
    await message.answer(ADMIN_TEXT, reply_markup=admin_inline_menu())

@dp.callback_query(F.data.startswith("adm_"))
async def admin_callbacks(call: types.CallbackQuery):
    if not await db.is_admin(call.from_user.id):
        return await call.answer("❌ Siz admin emassiz!", show_alert=True)

    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_home")]])
    action = call.data

    if action == "adm_home":
        text = ADMIN_TEXT
        markup = admin_inline_menu()
    elif action == "adm_stats":
        tot, act, blk = await db.get_stats()
        text = f"📊 <b>Bot Statistikasi:</b>\n\n👥 Jami: {tot}\n✅ Faol: {act}\n❌ Bloklaganlar: {blk}"
        markup = back
    elif action == "adm_channels":
        chs = await db.get_channels()
        text = "📢 <b>Ulangan kanallar:</b>\n\n"
        for c in chs:
            status = "Majburiy" if c["is_required"] else "Homiy"
            text += f"▪️ {c['title']} ({status}) | Limit: {c['target_subs']} | ID: {c['channel_id']}\n"
        if not chs:
            text = "Hozircha kanallar yo'q."
        text += "\n❌ O'chirish: <code>/del_channel ID</code>"
        markup = back
    elif action == "adm_refs":
        refs = await db.get_admin_refs()
        text = "📣 <b>Reklama referallari:</b>\n\n" + ("".join(f"Kodi: {r['_id']} - {r['count']} ta odam\n" for r in refs) or "Hozircha yo'q.")
        markup = back
    elif action == "adm_add":
        text = "🎬 <b>Kino qo'shish:</b>\n\nVideo yuboring va captionga yozing:\n<code>/add KODI | Nomi</code>\n\nMasalan: <code>/add 100 | Avatar</code>"
        markup = back
    elif action == "adm_post":
        text = "📝 <b>Post yaratish:</b>\n\nRasm yoki video yuboring va captionga yozing:\n<code>/post KODI | Matn</code>"
        markup = back
    elif action == "adm_broadcast":
        text = "📨 <b>Xabar tarqatish:</b>\n\nTarqatmoqchi bo'lgan xabarni yuboring, so'ng unga reply qilib <code>/broadcast</code> deb yozing."
        markup = back
    elif action == "adm_addch":
        text = ("➕ <b>Kanal qo'shish:</b>\n\n"
                "Majburiy: <code>/add_req_channel ID URL Limit Nomi</code>\n"
                "Homiy: <code>/add_opt_channel URL Nomi</code>\n"
                "Baza: <code>/add_baza ID Nomi</code>")
        markup = back
    else:
        return await call.answer()

    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:
        pass
    await call.answer()

@dp.message(F.text, ~F.text.startswith("/"))
async def search_movie_handler(message: types.Message):
    subbed, markup = await is_subscribed(message.from_user.id)
    if not subbed:
        markup.inline_keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_none")])
        return await message.answer("⚠️ Avval obuna bo'ling:", reply_markup=markup)

    text = message.text.strip()
    if text.isdigit():
        movie = await db.get_movie(text)
        if movie:
            return await send_movie(message, text)
    
    movies = await db.search_movies(text)
    if movies:
        res = "🔍 <b>Natijalar:</b>\n\n"
        for m in movies:
            res += f"🎬 {m['title']} - Kodi: <code>{m['_id']}</code>\n"
        await message.answer(res, reply_markup=await menu_for(message.from_user.id))
    else:
        await message.answer("❌ Hech narsa topilmadi.", reply_markup=await menu_for(message.from_user.id))

@dp.message(Command("my_refs"))
async def my_refs_cmd(message: types.Message):
    count = await db.get_user_refs_count(message.from_user.id)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"👥 <b>Sizning takliflaringiz:</b> {count} ta\n🔗 <b>Havolangiz:</b> {link}", reply_markup=await menu_for(message.from_user.id))

@dp.message(Command("add"))
async def add_movie_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    
    if not message.video or not message.caption:
        return await message.answer("❌ Iltimos, videoni tagiga shunday yozing: `/add Kodi | Nomi`", parse_mode="Markdown")
    
    try:
        cmd, args = message.caption.split(" ", 1)
        code, title = map(str.strip, args.split("|", 1))
        await db.add_movie(code, title, message.video.file_id)
        await message.reply(f"✅ Kino bazaga saqlandi!\nKodi: {code}\nNomi: {title}")
    except ValueError:
        await message.reply("❌ Format xato! Namuna: `/add 100 | Avatar`", parse_mode="Markdown")

@dp.message(Command("post"))
async def create_post_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    if not (message.photo or message.video) or not message.caption:
        return await message.reply("❌ Post yaratish uchun Rasm/Video jo'nating va captionga: `/post [KinoKodi] | [Matn]` deb yozing.", parse_mode="Markdown")

    try:
        cmd, args = message.caption.split(" ", 1)
        code, text = map(str.strip, args.split("|", 1))
        
        movie = await db.get_movie(code)
        if not movie:
            return await message.reply("❌ Bu kodli kino bazada yo'q! Avval /add qiling.")

        me = await bot.get_me()
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🍿 Kinoni ko'rish", url=f"https://t.me/{me.username}?start={code}")]
        ])

        baza_channels = await db.get_baza_channels()
        if not baza_channels:
            return await message.reply("❌ Baza kanallari qo'shilmagan! /add_baza buyrug'idan foydalaning.")

        count = 0
        for ch in baza_channels:
            try:
                await bot.copy_message(
                    chat_id=ch["channel_id"],
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    caption=text,
                    reply_markup=markup
                )
                count += 1
            except Exception as e:
                await message.reply(f"⚠️ {ch['title']} kanaliga yuborishda xatolik: {e}")
        
        await message.reply(f"✅ Post muvaffaqiyatli {count} ta kanalga yuborildi!")
    except Exception as e:
        await message.reply(f"❌ Xatolik yuz berdi. Format: `/post 101 | Ajoyib kino!`", parse_mode="Markdown")

@dp.message(Command("add_baza"))
async def add_baza_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    args = message.text.split(" ", 2)
    if len(args) < 3: return await message.reply("Xato! /add_baza [ID] [Nomi]")
    await db.add_baza_channel(int(args[1]), args[2])
    await message.reply("✅ Baza kanali qo'shildi! Bu yerga /post orqali postlar yuboriladi.")

@dp.message(Command("add_req_channel"))
async def add_req_channel_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    args = message.text.split(" ", 4)
    if len(args) < 5: return await message.reply("Xato! /add_req_channel [ID] [URL] [Limit] [Nomi]")
    await db.add_channel(int(args[1]), args[2], args[4], True, int(args[3]))
    channels_cache["last_updated"] = 0
    await message.reply("✅ Majburiy kanal qo'shildi!")

@dp.message(Command("add_opt_channel"))
async def add_opt_channel_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    args = message.text.split(" ", 2)
    if len(args) < 3: return await message.reply("Xato! /add_opt_channel [URL] [Nomi]")
    await db.add_channel(0, args[1], args[2], False, 0)
    channels_cache["last_updated"] = 0
    await message.reply("✅ Homiy (ixtiyoriy) kanal qo'shildi!")

@dp.message(Command("channels"))
async def channels_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    chs = await db.get_channels()
    res = "📢 <b>Ulangan kanallar:</b>\n\n"
    for c in chs:
        status = "Majburiy" if c["is_required"] else "Homiy"
        res += f"▪️ {c['title']} ({status}) | Limiti: {c['target_subs']} | ID: {c['channel_id']}\n"
    await message.reply(res)

@dp.message(Command("del_channel"))
async def del_channel_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    try:
        ch_id = int(message.text.split()[1])
        await db.delete_channel(ch_id)
        channels_cache["last_updated"] = 0
        await message.reply("✅ Kanal o'chirildi.")
    except:
        await message.reply("Xato! /del_channel [ID]")

@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    tot, act, blk = await db.get_stats()
    await message.reply(f"📊 <b>Bot Statistikasi:</b>\n\n👥 Jami: {tot}\n✅ Faol: {act}\n❌ Bloklaganlar: {blk}")

@dp.message(Command("admin"))
async def admin_panel_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id):
        return await message.answer("❌ Siz admin emassiz!")
    await message.answer("✅ Admin tugmasi menyuga qo'shildi.", reply_markup=await menu_for(message.from_user.id))
    await message.answer(ADMIN_TEXT, reply_markup=admin_inline_menu())

@dp.message(Command("admin_refs"))
async def admin_refs_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    refs = await db.get_admin_refs()
    res = "📣 <b>Reklama (Admin) referallari:</b>\n\n"
    for r in refs:
        res += f"Kodi: {r['_id']} - {r['count']} ta odam\n"
    await message.reply(res if refs else "Hozircha yo'q.")

@dp.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message):
    if not await db.is_admin(message.from_user.id): return
    if not message.reply_to_message:
        return await message.reply("❌ Tarqatish uchun xabarga 'reply' qilib /broadcast deb yozing.")
    
    await message.reply("📨 Xabar tarqatish boshlandi...")
    users_list = await db.get_all_users(active_only=True)
    success, fail = 0, 0
    
    for u in users_list:
        try:
            await bot.copy_message(chat_id=u["_id"], from_chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
            success += 1
            await asyncio.sleep(0.04) 
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.copy_message(chat_id=u["_id"], from_chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
            success += 1
        except TelegramForbiddenError:
            await db.update_user_status(u["_id"], False)
            fail += 1
        except Exception:
            fail += 1
            
    await message.reply(f"✅ <b>Tarqatish yakunlandi.</b>\n\nYuborildi: {success}\nBloklaganlar/Xatolar: {fail}")

@dp.message(Command("clean_db"))
async def clean_db_cmd(message: types.Message):
    if message.from_user.id != config.SUPER_ADMIN_ID: return
    deleted = await db.clean_blocked_users()
    await message.reply(f"🧹 Baza tozalandi. Jami {deleted} ta botni bloklagan(noaktiv) foydalanuvchilar bazadan o'chirildi.")

@dp.message(Command("backup"))
async def backup_cmd(message: types.Message):
    if message.from_user.id != config.SUPER_ADMIN_ID: return
    
    await message.reply("🔄 Backup tayyorlanmoqda...")
    users_data = await db.get_all_users()
    movies_data = await db.get_all_movies()
    
    backup_dict = {"users": users_data, "movies": movies_data}
    json_data = json.dumps(backup_dict, indent=4, default=str)
    
    file = BufferedInputFile(json_data.encode("utf-8"), filename="backup_kino_bot.json")
    await bot.send_document(message.chat.id, document=file, caption="✅ MongoDB Baza Zaxirasi")

@dp.message(Command("add_admin"))
async def super_add_admin(message: types.Message):
    if message.from_user.id != config.SUPER_ADMIN_ID: return
    try:
        new_id = int(message.text.split()[1])
        await db.add_admin(new_id)
        await message.reply(f"✅ {new_id} adminlar ro'yxatiga qo'shildi.")
    except:
        await message.reply("Xato! /add_admin [ID]")

@dp.message(Command("del_admin"))
async def super_del_admin(message: types.Message):
    if message.from_user.id != config.SUPER_ADMIN_ID: return
    try:
        del_id = int(message.text.split()[1])
        await db.del_admin(del_id)
        await message.reply(f"✅ {del_id} adminlikdan olindi.")
    except:
        await message.reply("Xato! /del_admin [ID]")

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(config.WEBHOOK_URL)
    print(f"Webhook set to {config.WEBHOOK_URL}")

@app.post("/webhook")
async def webhook_endpoint(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"status": "ok"}
