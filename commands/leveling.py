# commands/leveling.py — /rank, /xp, /leaderboard, /givexp, /removexp, /setxp, /resetxp

import discord
from discord import app_commands
from discord.ext import commands

from models.user_model import get_or_create_user
from services.xp_service import xp_progress, xp_for_level, make_progress_bar, calculate_level


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /rank ──────────────────────────────────────────────────────────────
    @app_commands.command(name="rank", description="Show your level and XP progress.")
    @app_commands.describe(member="The member to check (leave empty for yourself)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        user = await get_or_create_user(self.db, target.id, interaction.guild.id)

        level, xp_into, xp_needed = xp_progress(user["xp"])
        bar = make_progress_bar(xp_into, xp_needed, length=12)
        pct = int((xp_into / xp_needed) * 100)

        rank_pos = await self.db.users.count_documents({
            "guild_id": str(interaction.guild.id),
            "xp": {"$gt": user["xp"]},
        }) + 1

        embed = discord.Embed(
            title=f"📊 {target.display_name}'s Rank",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Server Rank", value=f"**#{rank_pos}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{user['xp']:,}**", inline=True)
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"`{bar}` {pct}%\n{xp_into:,} / {xp_needed:,} XP",
            inline=False,
        )
        embed.add_field(name="Messages", value=f"{user.get('messages', 0):,}", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /xp ───────────────────────────────────────────────────────────────
    @app_commands.command(name="xp", description="Show your exact XP total.")
    @app_commands.describe(member="The member to check")
    async def xp(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        user = await get_or_create_user(self.db, target.id, interaction.guild.id)
        await interaction.response.send_message(
            f"**{target.display_name}** has **{user['xp']:,} XP** total (Level {user['level']})."
        )

    # ── /leaderboard ──────────────────────────────────────────────────────
    @app_commands.command(name="leaderboard", description="Show the top 10 members by XP.")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cursor = self.db.users.find(
            {"guild_id": str(interaction.guild.id)},
            sort=[("xp", -1)],
            limit=10,
        )
        top = await cursor.to_list(length=10)

        if not top:
            await interaction.followup.send("No data yet! Start chatting to earn XP.")
            return

        embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, doc in enumerate(top):
            member = interaction.guild.get_member(int(doc["user_id"]))
            name = member.display_name if member else f"User {doc['user_id']}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{medal} **{name}** — Level {doc['level']} ({doc['xp']:,} XP)")

        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)

    # ── /givexp ───────────────────────────────────────────────────────────
    @app_commands.command(name="givexp", description="[Admin] Give XP to a member.")
    @app_commands.describe(member="Target member", amount="Amount of XP to give")
    @app_commands.checks.has_permissions(administrator=True)
    async def givexp(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        user = await get_or_create_user(self.db, member.id, interaction.guild.id)
        new_xp = user["xp"] + amount
        new_level = calculate_level(new_xp)
        old_level = user["level"]

        await self.db.users.update_one(
            {"user_id": str(member.id), "guild_id": str(interaction.guild.id)},
            {"$set": {"xp": new_xp, "level": new_level}},
            upsert=True,
        )

        leveled = "  🎉 They leveled up!" if new_level > old_level else ""
        embed = discord.Embed(
            description=f"✅ Gave **{amount:,} XP** to {member.mention}.\nThey now have **{new_xp:,} XP** (Level **{new_level}**).{leveled}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @givexp.error
    async def givexp_error(self, interaction, error):
        await interaction.response.send_message("You need Administrator permission.", ephemeral=True)

    # ── /removexp ─────────────────────────────────────────────────────────
    @app_commands.command(name="removexp", description="[Admin] Remove XP from a member.")
    @app_commands.describe(member="Target member", amount="Amount of XP to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def removexp(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        user = await get_or_create_user(self.db, member.id, interaction.guild.id)
        new_xp = max(0, user["xp"] - amount)
        new_level = calculate_level(new_xp)

        await self.db.users.update_one(
            {"user_id": str(member.id), "guild_id": str(interaction.guild.id)},
            {"$set": {"xp": new_xp, "level": new_level}},
        )

        embed = discord.Embed(
            description=f"✅ Removed **{amount:,} XP** from {member.mention}.\nThey now have **{new_xp:,} XP** (Level **{new_level}**).",
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @removexp.error
    async def removexp_error(self, interaction, error):
        await interaction.response.send_message("You need Administrator permission.", ephemeral=True)

    # ── /setxp ────────────────────────────────────────────────────────────
    @app_commands.command(name="setxp", description="[Admin] Set a member's XP to an exact amount.")
    @app_commands.describe(member="Target member", amount="Exact XP amount to set")
    @app_commands.checks.has_permissions(administrator=True)
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount < 0:
            await interaction.response.send_message("Amount can't be negative.", ephemeral=True)
            return

        new_level = calculate_level(amount)

        await self.db.users.update_one(
            {"user_id": str(member.id), "guild_id": str(interaction.guild.id)},
            {"$set": {"xp": amount, "level": new_level}},
            upsert=True,
        )

        embed = discord.Embed(
            description=f"✅ Set {member.mention}'s XP to **{amount:,}** (Level **{new_level}**).",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setxp.error
    async def setxp_error(self, interaction, error):
        await interaction.response.send_message("You need Administrator permission.", ephemeral=True)

    # ── /resetxp ──────────────────────────────────────────────────────────
    @app_commands.command(name="resetxp", description="[Admin] Reset a member's XP and level to zero.")
    @app_commands.describe(member="Target member")
    @app_commands.checks.has_permissions(administrator=True)
    async def resetxp(self, interaction: discord.Interaction, member: discord.Member):
        await self.db.users.update_one(
            {"user_id": str(member.id), "guild_id": str(interaction.guild.id)},
            {"$set": {"xp": 0, "level": 0, "messages": 0}},
            upsert=True,
        )
        await interaction.response.send_message(
            f"✅ Reset {member.mention}'s XP and level to **0**.", ephemeral=True
        )

    @resetxp.error
    async def resetxp_error(self, interaction, error):
        await interaction.response.send_message("You need Administrator permission.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Leveling(bot))