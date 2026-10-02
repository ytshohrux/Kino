import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, SUPER_ADMIN_ID

client = AsyncIOMotorClient(MONGO_URI)
db = client.kino_bot

users = db.users
movies = db.movies
channels = db.channels
baza_channels = db.baza_channels
admins = db.admins
admin_refs = db.admin_refs

class Database:
    @staticmethod
    async def get_user(user_id: int):
        return await users.find_one({"_id": user_id})

    @staticmethod
    async def add_user(user_id: int, full_name: str, username: str, referrer_id: int = None, admin_ref: str = None):
        user = await Database.get_user(user_id)
        if not user:
            await users.insert_one({
                "_id": user_id,
                "full_name": full_name,
                "username": username,
                "joined_at": asyncio.get_event_loop().time(),
                "referrer_id": referrer_id,
                "admin_ref": admin_ref,
                "is_active": True
            })
            return True
        elif not user.get("is_active"):
            await users.update_one({"_id": user_id}, {"$set": {"is_active": True}})
        return False

    @staticmethod
    async def update_user_status(user_id: int, status: bool):
        await users.update_one({"_id": user_id}, {"$set": {"is_active": status}})

    @staticmethod
    async def get_all_users(active_only=False):
        if active_only:
            return await users.find({"is_active": True}).to_list(length=None)
        return await users.find().to_list(length=None)

    @staticmethod
    async def get_stats():
        total = await users.count_documents({})
        active = await users.count_documents({"is_active": True})
        blocked = total - active
        return total, active, blocked

    @staticmethod
    async def clean_blocked_users():
        result = await users.delete_many({"is_active": False})
        return result.deleted_count

    # --- MOVIES ---
    @staticmethod
    async def add_movie(movie_code: str, title: str, file_id: str):
        await movies.update_one(
            {"_id": movie_code},
            {"$set": {"title": title, "file_id": file_id}},
            upsert=True
        )

    @staticmethod
    async def get_movie(movie_code: str):
        return await movies.find_one({"_id": movie_code})

    @staticmethod
    async def search_movies(query: str):
        return await movies.find({"title": {"$regex": query, "$options": "i"}}).limit(10).to_list(length=None)

    @staticmethod
    async def get_all_movies():
        return await movies.find().to_list(length=None)

    # --- CHANNELS ---
    @staticmethod
    async def add_channel(channel_id: int, url: str, title: str, is_required: bool, target_subs: int = 0):
        await channels.update_one(
            {"channel_id": channel_id},
            {"$set": {"url": url, "title": title, "is_required": is_required, "target_subs": target_subs}},
            upsert=True
        )

    @staticmethod
    async def delete_channel(channel_id: int):
        await channels.delete_one({"channel_id": channel_id})

    @staticmethod
    async def get_channels(required_only=False):
        query = {"is_required": True} if required_only else {}
        return await channels.find(query).to_list(length=None)

    @staticmethod
    async def update_channel_status(channel_id: int, is_required: bool):
        await channels.update_one({"channel_id": channel_id}, {"$set": {"is_required": is_required}})

    # --- BAZA CHANNELS ---
    @staticmethod
    async def add_baza_channel(channel_id: int, title: str):
        await baza_channels.update_one(
            {"channel_id": channel_id},
            {"$set": {"title": title}},
            upsert=True
        )

    @staticmethod
    async def get_baza_channels():
        return await baza_channels.find().to_list(length=None)
    
    @staticmethod
    async def delete_baza_channel(channel_id: int):
        await baza_channels.delete_one({"channel_id": channel_id})

    # --- ADMINS & REFERRALS ---
    @staticmethod
    async def is_admin(user_id: int):
        if user_id == SUPER_ADMIN_ID:
            return True
        admin = await admins.find_one({"_id": user_id})
        return bool(admin)

    @staticmethod
    async def add_admin(user_id: int):
        await admins.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)

    @staticmethod
    async def del_admin(user_id: int):
        await admins.delete_one({"_id": user_id})

    @staticmethod
    async def add_admin_ref(ref_code: str):
        await admin_refs.update_one({"_id": ref_code}, {"$inc": {"count": 1}}, upsert=True)

    @staticmethod
    async def get_admin_refs():
        return await admin_refs.find().to_list(length=None)

    @staticmethod
    async def get_user_refs_count(user_id: int):
        return await users.count_documents({"referrer_id": user_id})
