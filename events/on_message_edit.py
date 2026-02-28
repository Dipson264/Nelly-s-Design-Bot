# events/on_message_edit.py — Log message edits and deletions.

from datetime import datetime

import discord
from discord.ext import commands

import config


class OnMessageEdit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not config.MSG_LOG_CHANNEL:
            return
        if before.author.bot:
            return
        if before.content == after.content:
            return  # Embed-only update — skip

        ch = before.guild.get_channel(int(config.MSG_LOG_CHANNEL))
        if not ch:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Author",  value=f"{before.author} ({before.author.id})", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before",  value=before.content[:1024] or "(empty)", inline=False)
        embed.add_field(name="After",   value=after.content[:1024] or "(empty)", inline=False)
        embed.add_field(name="Jump",    value=f"[Jump to message]({after.jump_url})", inline=False)
        try:
            await ch.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not config.MSG_LOG_CHANNEL:
            return
        if message.author.bot:
            return
        if not message.guild:
            return

        ch = message.guild.get_channel(int(config.MSG_LOG_CHANNEL))
        if not ch:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Author",  value=f"{message.author} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content[:1024] or "(empty or attachment)", inline=False)
        try:
            await ch.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(OnMessageEdit(bot))
