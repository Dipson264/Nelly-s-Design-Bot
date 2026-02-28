# services/giveaway_service.py — Giveaway creation, entry, and winner selection.

import random
import re
from datetime import datetime, timedelta

import discord


def parse_duration(duration_str: str) -> datetime | None:
    """
    Parse a human-readable duration like '1d', '2h30m', '45m' into a future datetime.
    Returns None if the string is invalid.
    """
    pattern = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
    match = pattern.fullmatch(duration_str.strip())
    if not match or not any(match.groups()):
        return None
    days    = int(match.group(1) or 0)
    hours   = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if delta.total_seconds() <= 0:
        return None
    return datetime.utcnow() + delta


async def create_giveaway(db, guild_id: int, channel_id: int, message_id: int,
                           prize: str, winners_count: int, ends_at: datetime,
                           required_role: int | None = None,
                           min_level: int = 0,
                           bonus_entries: dict | None = None) -> dict:
    doc = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "message_id": str(message_id),
        "prize": prize,
        "winners_count": winners_count,
        "ends_at": ends_at,
        "ended": False,
        "required_role": str(required_role) if required_role else None,
        "min_level": min_level,
        "bonus_entries": bonus_entries or {},
        "entries": [],
        "winners": [],
    }
    await db.giveaways.insert_one(doc)
    return doc


async def toggle_entry(db, giveaway_id, user_id: str) -> tuple[bool, str]:
    """Add or remove a user from entries. Returns (entered, message)."""
    giveaway = await db.giveaways.find_one({"_id": giveaway_id})
    if not giveaway or giveaway["ended"]:
        return False, "This giveaway has ended."
    if user_id in giveaway["entries"]:
        await db.giveaways.update_one(
            {"_id": giveaway_id}, {"$pull": {"entries": user_id}}
        )
        return False, "You've left the giveaway."
    else:
        await db.giveaways.update_one(
            {"_id": giveaway_id}, {"$addToSet": {"entries": user_id}}
        )
        return True, "You've entered the giveaway!"


def pick_winners(giveaway: dict, member_roles: dict[str, list[str]], count: int | None = None) -> list[str]:
    """
    Select winners from the entry pool.
    member_roles = {user_id: [role_id, role_id, ...]}
    Applies bonus entries from giveaway['bonus_entries'].
    """
    pool = []
    for uid in giveaway["entries"]:
        weight = 1
        roles = member_roles.get(uid, [])
        for role_id, bonus in giveaway.get("bonus_entries", {}).items():
            if role_id in roles:
                weight += int(bonus)
        pool.extend([uid] * weight)

    n = count or giveaway["winners_count"]
    n = min(n, len(set(giveaway["entries"])))
    if not pool:
        return []
    # Sample without replacement from pool (weighted)
    winners = []
    seen = set()
    random.shuffle(pool)
    for uid in pool:
        if uid not in seen:
            winners.append(uid)
            seen.add(uid)
        if len(winners) >= n:
            break
    return winners


async def end_giveaway(db, giveaway: dict, guild: discord.Guild) -> list[str]:
    """Mark giveaway ended, pick winners, update embed, return winner IDs."""
    from bson import ObjectId

    # Build role map for bonus entries
    member_roles: dict[str, list[str]] = {}
    for uid in giveaway["entries"]:
        member = guild.get_member(int(uid))
        if member:
            member_roles[uid] = [str(r.id) for r in member.roles]

    winners = pick_winners(giveaway, member_roles)
    await db.giveaways.update_one(
        {"_id": giveaway["_id"]},
        {"$set": {"ended": True, "winners": winners}},
    )
    return winners
