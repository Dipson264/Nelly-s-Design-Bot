# services/economy_service.py — All economy/currency logic.

import random
from datetime import datetime, date

import config
from models.user_model import get_or_create_user


async def get_balance(db, user_id: int, guild_id: int) -> dict:
    user = await get_or_create_user(db, user_id, guild_id)
    return {"balance": user["balance"], "bank": user["bank"]}


async def add_coins(db, user_id: int, guild_id: int, amount: int):
    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": amount}},
        upsert=True,
    )


async def remove_coins(db, user_id: int, guild_id: int, amount: int) -> bool:
    """Remove coins from wallet. Returns False if insufficient funds."""
    user = await get_or_create_user(db, user_id, guild_id)
    if user["balance"] < amount:
        return False
    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": -amount}},
    )
    return True


async def set_coins(db, user_id: int, guild_id: int, amount: int):
    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$set": {"balance": amount}},
        upsert=True,
    )


async def deposit(db, user_id: int, guild_id: int, amount: int) -> tuple[bool, str]:
    user = await get_or_create_user(db, user_id, guild_id)
    if amount <= 0:
        return False, "Amount must be positive."
    if user["balance"] < amount:
        return False, f"You only have {user['balance']} {config.CURRENCY_NAME} in your wallet."
    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": -amount, "bank": amount}},
    )
    return True, f"Deposited {amount} {config.CURRENCY_NAME} into your bank."


async def withdraw(db, user_id: int, guild_id: int, amount: int) -> tuple[bool, str]:
    user = await get_or_create_user(db, user_id, guild_id)
    if amount <= 0:
        return False, "Amount must be positive."
    if user["bank"] < amount:
        return False, f"You only have {user['bank']} {config.CURRENCY_NAME} in your bank."
    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": amount, "bank": -amount}},
    )
    return True, f"Withdrew {amount} {config.CURRENCY_NAME} from your bank."


async def pay(db, sender_id: int, receiver_id: int, guild_id: int, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be positive."
    sender = await get_or_create_user(db, sender_id, guild_id)
    if sender["balance"] < amount:
        return False, f"You only have {sender['balance']} {config.CURRENCY_NAME}."
    await db.users.update_one(
        {"user_id": str(sender_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": -amount}},
    )
    await db.users.update_one(
        {"user_id": str(receiver_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": amount}},
        upsert=True,
    )
    return True, f"Paid {amount} {config.CURRENCY_NAME}."


async def claim_daily(db, user_id: int, guild_id: int) -> tuple[bool, str, int]:
    """Returns (success, message, seconds_remaining)."""
    user = await get_or_create_user(db, user_id, guild_id)
    now = datetime.utcnow()
    if user["last_daily"]:
        elapsed = (now - user["last_daily"]).total_seconds()
        remaining = config.DAILY_COOLDOWN - elapsed
        if remaining > 0:
            hours, rem = divmod(int(remaining), 3600)
            mins = rem // 60
            return False, f"Come back in **{hours}h {mins}m**.", int(remaining)
    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": config.DAILY_AMOUNT}, "$set": {"last_daily": now}},
        upsert=True,
    )
    return True, f"You claimed your daily **{config.DAILY_AMOUNT} {config.CURRENCY_NAME}**!", 0


async def do_work(db, user_id: int, guild_id: int) -> tuple[bool, str, int]:
    """Returns (success, message, seconds_remaining)."""
    user = await get_or_create_user(db, user_id, guild_id)
    now = datetime.utcnow()
    if user["last_work"]:
        elapsed = (now - user["last_work"]).total_seconds()
        remaining = config.WORK_COOLDOWN - elapsed
        if remaining > 0:
            mins = int(remaining // 60)
            return False, f"You're tired. Come back in **{mins}m**.", int(remaining)
    earned = random.randint(config.WORK_MIN, config.WORK_MAX)
    jobs = [
        f"You delivered pizzas and earned **{earned} {config.CURRENCY_NAME}**! 🍕",
        f"You coded all night and earned **{earned} {config.CURRENCY_NAME}**! 💻",
        f"You walked dogs and earned **{earned} {config.CURRENCY_NAME}**! 🐕",
        f"You mined crypto and earned **{earned} {config.CURRENCY_NAME}**! ⛏️",
        f"You designed logos and earned **{earned} {config.CURRENCY_NAME}**! 🎨",
    ]
    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$inc": {"balance": earned}, "$set": {"last_work": now}},
        upsert=True,
    )
    return True, random.choice(jobs), 0


async def process_chat_coins(db, user_id: int, guild_id: int):
    """Award small coins per message with a daily cap."""
    if not config.ECONOMY_ENABLED:
        return
    user = await get_or_create_user(db, user_id, guild_id)
    today = date.today().isoformat()

    # Reset daily cap if it's a new day
    updates = {}
    if user.get("daily_chat_reset") != today:
        updates["daily_chat_coins"] = 0
        updates["daily_chat_reset"] = today
        current_chat_coins = 0
    else:
        current_chat_coins = user.get("daily_chat_coins", 0)

    if current_chat_coins >= config.MAX_DAILY_CHAT_COINS:
        return

    earned = random.randint(config.CHAT_COINS_MIN, config.CHAT_COINS_MAX)
    updates_set = {"$inc": {"balance": earned, "daily_chat_coins": earned}}
    if updates:
        updates_set["$set"] = updates

    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        updates_set,
        upsert=True,
    )


async def get_shop(db, guild_id: int) -> list:
    guild = await db.guilds.find_one({"guild_id": str(guild_id)})
    if not guild:
        return []
    return guild.get("shop_items", [])


async def buy_item(db, user_id: int, guild_id: int, item_id: str) -> tuple[bool, str]:
    shop = await get_shop(db, guild_id)
    item = next((i for i in shop if i["id"] == item_id), None)
    if not item:
        return False, "Item not found in the shop."
    removed = await remove_coins(db, user_id, guild_id, item["price"])
    if not removed:
        return False, f"You don't have enough {config.CURRENCY_NAME}."

    inv_entry = {"item_id": item["id"], "name": item["name"], "type": item["type"]}
    if item.get("duration_hours"):
        from datetime import timedelta
        inv_entry["expires"] = datetime.utcnow() + timedelta(hours=item["duration_hours"])
    else:
        inv_entry["expires"] = None

    await db.users.update_one(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        {"$push": {"inventory": inv_entry}},
        upsert=True,
    )
    return True, item
