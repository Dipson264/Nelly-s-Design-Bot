# commands/moderation.py — /warn, /warnings, /kick, /ban, /mute, /unmute, /clear

import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from services.moderation_service import (
    add_warning, get_warnings, clear_warnings, send_mod_log
)


def parse_duration_to_delta(s: str) -> timedelta | None:
    pattern = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
    m = pattern.fullmatch(s.strip())
    if not m or not any(m.groups()):
        return None
    d = int(m.group(1) or 0)
    h = int(m.group(2) or 0)
    mn = int(m.group(3) or 0)
    sc = int(m.group(4) or 0)
    delta = timedelta(days=d, hours=h, minutes=mn, seconds=sc)
    return delta if delta.total_seconds() > 0 else None


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /warn ─────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member.")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.checks.has_permissions(kick_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't warn yourself.", ephemeral=True)
            return
        if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You can't warn someone with an equal or higher role.", ephemeral=True)
            return

        await add_warning(self.db, member.id, interaction.guild.id, reason, interaction.user.id)

        # DM the warned user
        try:
            await member.send(
                embed=discord.Embed(
                    title="⚠️ You have been warned",
                    description=f"**Server:** {interaction.guild.name}\n**Reason:** {reason}",
                    color=discord.Color.yellow(),
                )
            )
        except discord.Forbidden:
            pass

        # Count warnings
        warnings = await get_warnings(self.db, member.id, interaction.guild.id)
        embed = discord.Embed(
            description=f"⚠️ **{member}** has been warned. They now have **{len(warnings)}** warning(s).\n**Reason:** {reason}",
            color=discord.Color.yellow(),
        )
        await interaction.response.send_message(embed=embed)
        await send_mod_log(interaction.guild, "Warn", member, interaction.user, reason, discord.Color.yellow())

    @warn.error
    async def warn_error(self, interaction, error):
        await interaction.response.send_message("You need Kick Members permission.", ephemeral=True)

    # ── /warnings ─────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="View a member's warnings.")
    @app_commands.describe(member="Member to check")
    @app_commands.checks.has_permissions(kick_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        warns = await get_warnings(self.db, member.id, interaction.guild.id)
        if not warns:
            await interaction.response.send_message(f"**{member}** has no warnings.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"⚠️ Warnings for {member}",
            color=discord.Color.orange(),
        )
        for i, w in enumerate(warns[:10], 1):
            mod = interaction.guild.get_member(int(w["moderator_id"]))
            mod_name = str(mod) if mod else w["moderator_id"]
            ts = w["timestamp"].strftime("%Y-%m-%d %H:%M")
            embed.add_field(
                name=f"#{i} — {ts}",
                value=f"**Reason:** {w['reason']}\n**By:** {mod_name}",
                inline=False,
            )
        embed.set_footer(text=f"Total warnings: {len(warns)}")
        await interaction.response.send_message(embed=embed)

    @warnings.error
    async def warnings_error(self, interaction, error):
        await interaction.response.send_message("You need Kick Members permission.", ephemeral=True)

    # ── /clearwarnings ────────────────────────────────────────────────────
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.describe(member="Member to clear warnings for")
    @app_commands.checks.has_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        count = await clear_warnings(self.db, member.id, interaction.guild.id)
        await interaction.response.send_message(
            f"Cleared **{count}** warning(s) for {member.mention}.", ephemeral=True
        )

    @clearwarnings.error
    async def clearwarnings_error(self, interaction, error):
        await interaction.response.send_message("You need Administrator permission.", ephemeral=True)

    # ── /kick ─────────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("I can't kick that member (role hierarchy).", ephemeral=True)
            return
        try:
            await member.send(
                embed=discord.Embed(
                    title="👢 You have been kicked",
                    description=f"**Server:** {interaction.guild.name}\n**Reason:** {reason}",
                    color=discord.Color.orange(),
                )
            )
        except discord.Forbidden:
            pass
        await member.kick(reason=reason)
        embed = discord.Embed(
            description=f"👢 **{member}** has been kicked.\n**Reason:** {reason}",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)
        await send_mod_log(interaction.guild, "Kick", member, interaction.user, reason, discord.Color.orange())

    @kick.error
    async def kick_error(self, interaction, error):
        await interaction.response.send_message("You need Kick Members permission.", ephemeral=True)

    # ── /ban ──────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(member="Member to ban", reason="Reason for ban", delete_days="Days of messages to delete (0-7)")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  reason: str = "No reason provided", delete_days: int = 0):
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("I can't ban that member (role hierarchy).", ephemeral=True)
            return
        try:
            await member.send(
                embed=discord.Embed(
                    title="🔨 You have been banned",
                    description=f"**Server:** {interaction.guild.name}\n**Reason:** {reason}",
                    color=discord.Color.red(),
                )
            )
        except discord.Forbidden:
            pass
        await member.ban(reason=reason, delete_message_days=max(0, min(delete_days, 7)))
        embed = discord.Embed(
            description=f"🔨 **{member}** has been banned.\n**Reason:** {reason}",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed)
        await send_mod_log(interaction.guild, "Ban", member, interaction.user, reason, discord.Color.red())

    @ban.error
    async def ban_error(self, interaction, error):
        await interaction.response.send_message("You need Ban Members permission.", ephemeral=True)

    # ── /mute (timeout) ───────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout (mute) a member.")
    @app_commands.describe(member="Member to mute", duration="Duration e.g. 10m, 1h, 1d", reason="Reason")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member,
                   duration: str = "10m", reason: str = "No reason provided"):
        delta = parse_duration_to_delta(duration)
        if not delta:
            await interaction.response.send_message("Invalid duration. Use `10m`, `1h`, `1d` etc.", ephemeral=True)
            return
        until = discord.utils.utcnow() + delta
        try:
            await member.timeout(until, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to timeout that member.", ephemeral=True)
            return
        embed = discord.Embed(
            description=f"🔇 **{member}** has been muted for **{duration}**.\n**Reason:** {reason}",
            color=discord.Color.dark_grey(),
        )
        await interaction.response.send_message(embed=embed)
        await send_mod_log(interaction.guild, f"Mute ({duration})", member, interaction.user, reason, discord.Color.dark_grey())

    @mute.error
    async def mute_error(self, interaction, error):
        await interaction.response.send_message("You need Moderate Members permission.", ephemeral=True)

    # ── /unmute ───────────────────────────────────────────────────────────
    @app_commands.command(name="unmute", description="Remove timeout from a member.")
    @app_commands.describe(member="Member to unmute")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.timeout(None, reason=f"Unmuted by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to remove that timeout.", ephemeral=True)
            return
        await interaction.response.send_message(f"🔊 **{member}** has been unmuted.")
        await send_mod_log(interaction.guild, "Unmute", member, interaction.user, "Unmuted", discord.Color.green())

    @unmute.error
    async def unmute_error(self, interaction, error):
        await interaction.response.send_message("You need Moderate Members permission.", ephemeral=True)

    # ── /clear ────────────────────────────────────────────────────────────
    @app_commands.command(name="clear", description="Delete messages from this channel.")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if not 1 <= amount <= 100:
            await interaction.response.send_message("Amount must be between 1 and 100.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** message(s).", ephemeral=True)

    @clear.error
    async def clear_error(self, interaction, error):
        await interaction.response.send_message("You need Manage Messages permission.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
