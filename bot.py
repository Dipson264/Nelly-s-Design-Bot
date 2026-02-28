# bot.py — Entry point. Run this file to start the bot: python bot.py

import asyncio
import logging
import os
from datetime import datetime

import discord
import motor.motor_asyncio
from discord.ext import commands

import config

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("bot")

# ── Intents ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True   # Required: enable in Discord Dev Portal
intents.members = True           # Required: enable in Discord Dev Portal


class CommunityBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",   # Prefix is unused (we use slash commands) but required
            intents=intents,
            help_command=None,    # We have our own /help
        )
        self.db = None
        self.start_time = datetime.utcnow()

    async def setup_hook(self):
        """Called automatically before the bot connects. Load cogs and DB here."""
        await self.connect_database()
        await self.load_cogs()
        # Sync slash commands to Discord
        await self.tree.sync()
        log.info("Slash commands synced.")

    async def connect_database(self):
        """Connect to MongoDB and create indexes for performance."""
        client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
        self.db = client["discord_bot"]

        # Indexes — these make queries fast even with millions of records
        await self.db.users.create_index(
            [("user_id", 1), ("guild_id", 1)], unique=True
        )
        await self.db.users.create_index([("guild_id", 1), ("xp", -1)])
        await self.db.users.create_index([("guild_id", 1), ("balance", -1)])
        await self.db.warnings.create_index([("user_id", 1), ("guild_id", 1)])
        await self.db.giveaways.create_index([("guild_id", 1), ("ended", 1)])
        await self.db.tickets.create_index([("user_id", 1), ("guild_id", 1)])
        log.info("Connected to MongoDB and ensured indexes.")

    async def load_cogs(self):
        """Load all command and event cogs."""
        cogs = [
            "commands.leveling",
            "commands.economy",
            "commands.giveaways",
            "commands.tickets",
            "commands.moderation",
            "commands.autoroles",
            "commands.utility",
            "events.on_message",
            "events.on_member_join",
            "events.on_member_remove",
            "events.on_message_edit",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | /help"
            )
        )


async def main():
    async with CommunityBot() as bot:
        await bot.start(config.BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
