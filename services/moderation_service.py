# services/moderation_service.py — Warning storage and auto-mod logic.

import re
from datetime import datetime
from collections import defaultdict, deque

import discord

import config


# In-memory spam tracker: {(guild_id, user_id): deque of timestamps}
_spam_tracker: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=10))
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


async def add_warning(db, user_id: int, guild_id: int, reason: str, moderator_id: int) -> dict:
    doc = {
        "user_id": str(user_id),
        "guild_id": str(guild_id),
        "reason": reason,
        "moderator_id": str(moderator_id),
        "timestamp": datetime.utcnow(),
    }
    await db.warnings.insert_one(doc)
    return doc


async def get_warnings(db, user_id: int, guild_id: int) -> list:
    cursor = db.warnings.find(
        {"user_id": str(user_id), "guild_id": str(guild_id)},
        sort=[("timestamp", -1)],
    )
    return await cursor.to_list(length=50)


async def clear_warnings(db, user_id: int, guild_id: int) -> int:
    result = await db.warnings.delete_many(
        {"user_id": str(user_id), "guild_id": str(guild_id)}
    )
    return result.deleted_count


def is_staff(member: discord.Member) -> bool:
    """Check if member has a staff role or is an admin."""
    if member.guild_permissions.administrator:
        return True
    return any(r.id in config.STAFF_ROLE_IDS for r in member.roles)


async def check_automod(message: discord.Message) -> bool:
    """
    Run auto-moderation checks. Returns True if message was deleted.
    Checks: blacklisted words, anti-link, anti-spam.
    """
    if not config.MODERATION_ENABLED:
        return False
    if is_staff(message.author):
        return False

    content_lower = message.content.lower()

    # Blacklisted words
    for word in config.BLACKLISTED_WORDS:
        if word.lower() in content_lower:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} Your message contained a blacklisted word.",
                    delete_after=5,
                )
            except discord.Forbidden:
                pass
            return True

    # Anti-link
    if config.ANTI_LINK_ENABLED and URL_PATTERN.search(message.content):
        try:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} Links are not allowed here.",
                delete_after=5,
            )
        except discord.Forbidden:
            pass
        return True

    # Anti-spam
    key = (message.guild.id, message.author.id)
    now = datetime.utcnow().timestamp()
    tracker = _spam_tracker[key]
    tracker.append(now)

    recent = [t for t in tracker if now - t <= 5]
    if len(recent) >= config.ANTI_SPAM_THRESHOLD:
        try:
            await message.delete()
            await message.author.timeout(
                discord.utils.utcnow() + __import__("datetime").timedelta(seconds=30),
                reason="Auto-mod: Spamming",
            )
            await message.channel.send(
                f"{message.author.mention} Slow down! You've been muted for 30 seconds.",
                delete_after=8,
            )
        except discord.Forbidden:
            pass
        return True

    return False


async def send_mod_log(guild: discord.Guild, action: str, target: discord.User,
                       moderator: discord.Member, reason: str, color: discord.Color):
    """Post a moderation action embed to the mod log channel."""
    if not config.MOD_LOG_CHANNEL:
        return
    ch = guild.get_channel(int(config.MOD_LOG_CHANNEL))
    if not ch:
        return
    embed = discord.Embed(title=f"🔨 {action}", color=color, timestamp=datetime.utcnow())
    embed.add_field(name="User", value=f"{target} ({target.id})", inline=True)
    embed.add_field(name="Moderator", value=f"{moderator} ({moderator.id})", inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    try:
        await ch.send(embed=embed)
    except discord.Forbidden:
        pass
