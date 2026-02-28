# models/user_model.py — Helper functions for the users collection.

from datetime import datetime


def default_user(user_id: str, guild_id: str) -> dict:
    """Returns a fresh user document with all default values."""
    return {
        "user_id": user_id,
        "guild_id": guild_id,
        # Leveling
        "xp": 0,
        "level": 0,
        "messages": 0,
        "last_xp_time": None,
        # Economy
        "balance": 0,
        "bank": 0,
        "last_daily": None,
        "last_work": None,
        "daily_chat_coins": 0,
        "daily_chat_reset": datetime.utcnow().date().isoformat(),
        # Inventory
        "inventory": [],
        # Meta
        "created_at": datetime.utcnow(),
    }


async def get_or_create_user(db, user_id: int, guild_id: int) -> dict:
    """Fetch a user document, creating it with defaults if it doesn't exist."""
    uid, gid = str(user_id), str(guild_id)
    user = await db.users.find_one({"user_id": uid, "guild_id": gid})
    if not user:
        doc = default_user(uid, gid)
        await db.users.insert_one(doc)
        user = await db.users.find_one({"user_id": uid, "guild_id": gid})
    return user
