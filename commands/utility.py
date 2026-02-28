# commands/utility.py — /ping, /uptime, /botinfo, /help

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /ping ─────────────────────────────────────────────────────────────
    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency < 100 else discord.Color.yellow() if latency < 200 else discord.Color.red()
        await interaction.response.send_message(
            embed=discord.Embed(description=f"🏓 Pong! **{latency}ms**", color=color)
        )

    # ── /uptime ───────────────────────────────────────────────────────────
    @app_commands.command(name="uptime", description="Show how long the bot has been running.")
    async def uptime(self, interaction: discord.Interaction):
        delta = datetime.utcnow() - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        parts = []
        if days:    parts.append(f"{days}d")
        if hours:   parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"⏱️ Bot has been online for **{' '.join(parts)}**.",
                color=discord.Color.blurple(),
            )
        )

    # ── /botinfo ──────────────────────────────────────────────────────────
    @app_commands.command(name="botinfo", description="Show information about the bot.")
    async def botinfo(self, interaction: discord.Interaction):
        bot = self.bot
        embed = discord.Embed(title=f"ℹ️ {bot.user.name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name="Servers",   value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Users",     value=str(sum(g.member_count for g in bot.guilds)), inline=True)
        embed.add_field(name="Latency",   value=f"{round(bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Bot ID",    value=str(bot.user.id), inline=True)
        embed.add_field(name="Library",   value="discord.py 2.x", inline=True)
        embed.add_field(name="Database",  value="MongoDB (motor)", inline=True)
        embed.set_footer(text="Modular Community Bot")
        await interaction.response.send_message(embed=embed)

    # ── /help ─────────────────────────────────────────────────────────────
    @app_commands.command(name="help", description="Show all available commands.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Command List",
            description="All commands use `/` slash prefix.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="⭐ Leveling",
            value="`/rank` `/xp` `/leaderboard`",
            inline=False,
        )
        embed.add_field(
            name="💰 Economy",
            value="`/balance` `/daily` `/work` `/deposit` `/withdraw` `/pay` `/baltop` `/shop` `/buy` `/inventory`",
            inline=False,
        )
        embed.add_field(
            name="🎉 Giveaways",
            value="`/gcreate` `/gend` `/greroll` `/glist`",
            inline=False,
        )
        embed.add_field(
            name="🎫 Tickets",
            value="`/ticketpanel` `/close`",
            inline=False,
        )
        embed.add_field(
            name="🔨 Moderation",
            value="`/warn` `/warnings` `/clearwarnings` `/kick` `/ban` `/mute` `/unmute` `/clear`",
            inline=False,
        )
        embed.add_field(
            name="🏷️ Roles",
            value="`/rolepanel` `/giverole`",
            inline=False,
        )
        embed.add_field(
            name="🤖 Admin — Economy",
            value="`/addcoins` `/removecoins` `/setcoins` `/reseteconomy`",
            inline=False,
        )
        embed.add_field(
            name="🔧 Utility",
            value="`/ping` `/uptime` `/botinfo` `/help`",
            inline=False,
        )
        embed.set_footer(text="Admin commands require Administrator or relevant permissions.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Utility(bot))
