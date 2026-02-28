# services/xp_service.py — All XP and leveling logic lives here.

import random
from datetime import datetime

import discord

import config
from models.user_model import get_or_create_user


def xp_for_level(level: int) -> int:
    """Total XP required to REACH a given level."""
    return 5 * (level ** 2) + 50 * level + 100


def calculate_level(total_xp: int) -> int:
    """Given total XP, return the current level."""
    level = 0
    while total_xp >= xp_for_level(level + 1):
        level += 1
    return level


def xp_progress(total_xp: int) -> tuple[int, int, int]:
    """Returns (current_level, xp_into_level, xp_needed_for_next_level)."""
    level = calculate_level(total_xp)
    xp_start = xp_for_level(level)
    xp_end   = xp_for_level(level + 1)
    return level, total_xp - xp_start, xp_end - xp_start


def make_progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int((current / total) * length)
    return "█" * filled + "░" * (length - filled)


async def process_message_xp(db, message: discord.Message):
    """Called on every non-bot message. Handles cooldown, XP grant, level-up."""
    if not config.LEVELING_ENABLED:
        return
    if message.channel.id in config.XP_IGNORED_CHANNELS:
        return

    user = await get_or_create_user(db, message.author.id, message.guild.id)
    now = datetime.utcnow()

    # Cooldown check
    if user["last_xp_time"]:
        elapsed = (now - user["last_xp_time"]).total_seconds()
        if elapsed < config.XP_COOLDOWN_SECONDS:
            return

    xp_gain  = random.randint(config.XP_MIN_PER_MESSAGE, config.XP_MAX_PER_MESSAGE)
    new_xp   = user["xp"] + xp_gain
    new_level = calculate_level(new_xp)
    old_level = user["level"]

    await db.users.update_one(
        {"user_id": str(message.author.id), "guild_id": str(message.guild.id)},
        {
            "$set": {
                "xp": new_xp,
                "level": new_level,
                "last_xp_time": now,
            },
            "$inc": {"messages": 1},
        },
        upsert=True,
    )

    if new_level > old_level:
        await handle_level_up(db, message, new_level)


async def handle_level_up(db, message: discord.Message, new_level: int):
    """Send a level-up message and assign any role rewards."""
    embed = discord.Embed(
        title="⬆️ Level Up!",
        description=f"**{message.author.mention}** reached **Level {new_level}**! 🎉",
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=message.author.display_avatar.url)

    # Send to configured channel or DM
    channel_id = config.LEVEL_UP_CHANNEL
    try:
        if channel_id:
            ch = message.guild.get_channel(int(channel_id))
            if ch:
                await ch.send(embed=embed)
        else:
            await message.author.send(embed=embed)
    except discord.Forbidden:
        pass  # DMs closed — silently skip

    # Role reward
    role_id = config.LEVEL_ROLES.get(new_level)
    if role_id:
        role = message.guild.get_role(role_id)
        if role:
            try:
                if not config.STACK_LEVEL_ROLES:
                    # Remove all previous level roles
                    for lvl, rid in config.LEVEL_ROLES.items():
                        if lvl < new_level:
                            old_role = message.guild.get_role(rid)
                            if old_role and old_role in message.author.roles:
                                await message.author.remove_roles(old_role)
                await message.author.add_roles(role, reason=f"Reached level {new_level}")
            except discord.Forbidden:
                pass
