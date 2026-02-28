# events/on_member_remove.py — Leave log.

from datetime import datetime

import discord
from discord.ext import commands

import config


class OnMemberRemove(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not config.JOIN_LOG_CHANNEL:
            return
        ch = member.guild.get_channel(int(config.JOIN_LOG_CHANNEL))
        if not ch:
            return

        embed = discord.Embed(
            title="❌ Member Left",
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User",    value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Joined",  value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(member.guild.member_count), inline=True)
        try:
            await ch.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(OnMemberRemove(bot))
