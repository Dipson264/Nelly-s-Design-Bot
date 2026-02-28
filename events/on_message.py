# events/on_message.py — Fires on every message. Handles XP, coins, auto-mod.

import discord
from discord.ext import commands

import config
from services.xp_service import process_message_xp
from services.economy_service import process_chat_coins
from services.moderation_service import check_automod


class OnMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore DMs, bots, and system messages
        if not message.guild:
            return
        if message.author.bot:
            return
        if message.type != discord.MessageType.default:
            return

        # Auto-moderation (runs first — if message deleted, skip XP)
        deleted = await check_automod(message)
        if deleted:
            return

        # Grant XP
        if config.LEVELING_ENABLED:
            await process_message_xp(self.bot.db, message)

        # Grant chat coins
        if config.ECONOMY_ENABLED:
            await process_chat_coins(self.bot.db, message.author.id, message.guild.id)


async def setup(bot):
    await bot.add_cog(OnMessage(bot))
