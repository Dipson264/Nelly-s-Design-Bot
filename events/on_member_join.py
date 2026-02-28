# events/on_member_join.py — Auto-role on join + join log.

from datetime import datetime

import discord
from discord.ext import commands

import config


class OnMemberJoin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Auto-assign join role
        if config.AUTO_JOIN_ROLE:
            role = member.guild.get_role(int(config.AUTO_JOIN_ROLE))
            if role:
                try:
                    await member.add_roles(role, reason="Auto join role")
                except discord.Forbidden:
                    pass

        # Join log
        if config.JOIN_LOG_CHANNEL:
            ch = member.guild.get_channel(int(config.JOIN_LOG_CHANNEL))
            if ch:
                embed = discord.Embed(
                    title="✅ Member Joined",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow(),
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="User",    value=f"{member} ({member.id})", inline=False)
                embed.add_field(name="Account", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
                embed.add_field(name="Members", value=str(member.guild.member_count), inline=True)
                try:
                    await ch.send(embed=embed)
                except discord.Forbidden:
                    pass


async def setup(bot):
    await bot.add_cog(OnMemberJoin(bot))
