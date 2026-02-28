# commands/giveaways.py — /gcreate, /gend, /greroll, /glist

import asyncio
from datetime import datetime

import discord
from bson import ObjectId
from discord import app_commands
from discord.ext import commands, tasks

import config
from services.giveaway_service import (
    create_giveaway, end_giveaway, parse_duration, pick_winners
)


def giveaway_embed(prize: str, ends_at: datetime, winners_count: int,
                   entries: list, ended: bool = False, winners: list = None) -> discord.Embed:
    color = discord.Color.green() if not ended else discord.Color.greyple()
    embed = discord.Embed(
        title=f"{config.GIVEAWAY_EMOJI} Giveaway: {prize}",
        color=color,
    )
    if not ended:
        embed.add_field(name="Ends", value=f"<t:{int(ends_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Winners", value=str(winners_count), inline=True)
        embed.add_field(name="Entries", value=str(len(entries)), inline=True)
        embed.set_footer(text="Click the button below to enter!")
    else:
        if winners:
            winner_mentions = ", ".join(f"<@{w}>" for w in winners)
            embed.description = f"**Winner(s):** {winner_mentions}"
        else:
            embed.description = "No valid entries — no winners."
        embed.set_footer(text="Giveaway ended")
    return embed


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enter Giveaway",
        style=discord.ButtonStyle.green,
        emoji="🎉",
        custom_id="giveaway_enter",
    )
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db
        giveaway = await db.giveaways.find_one({
            "message_id": str(interaction.message.id),
            "guild_id": str(interaction.guild.id),
        })
        if not giveaway:
            await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            return
        if giveaway["ended"]:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return

        # Check requirements
        if giveaway.get("required_role"):
            role = interaction.guild.get_role(int(giveaway["required_role"]))
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(
                    f"You need the **{role.name}** role to enter.", ephemeral=True
                )
                return

        if giveaway.get("min_level", 0) > 0:
            user_doc = await db.users.find_one({
                "user_id": str(interaction.user.id),
                "guild_id": str(interaction.guild.id),
            })
            user_level = user_doc["level"] if user_doc else 0
            if user_level < giveaway["min_level"]:
                await interaction.response.send_message(
                    f"You need to be at least Level **{giveaway['min_level']}** to enter.", ephemeral=True
                )
                return

        uid = str(interaction.user.id)
        if uid in giveaway["entries"]:
            await db.giveaways.update_one(
                {"_id": giveaway["_id"]}, {"$pull": {"entries": uid}}
            )
            await interaction.response.send_message("❌ You left the giveaway.", ephemeral=True)
        else:
            await db.giveaways.update_one(
                {"_id": giveaway["_id"]}, {"$addToSet": {"entries": uid}}
            )
            await interaction.response.send_message("✅ You entered the giveaway!", ephemeral=True)

        # Refresh entry count on embed
        updated = await db.giveaways.find_one({"_id": giveaway["_id"]})
        embed = giveaway_embed(
            updated["prize"], updated["ends_at"],
            updated["winners_count"], updated["entries"]
        )
        await interaction.message.edit(embed=embed, view=self)


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    @property
    def db(self):
        return self.bot.db

    def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        """Automatically end giveaways when their time is up."""
        now = datetime.utcnow()
        cursor = self.db.giveaways.find({
            "ended": False,
            "ends_at": {"$lte": now},
        })
        async for giveaway in cursor:
            guild = self.bot.get_guild(int(giveaway["guild_id"]))
            if not guild:
                continue
            channel = guild.get_channel(int(giveaway["channel_id"]))
            if not channel:
                continue
            try:
                message = await channel.fetch_message(int(giveaway["message_id"]))
            except discord.NotFound:
                continue

            winners = await end_giveaway(self.db, giveaway, guild)
            embed = giveaway_embed(
                giveaway["prize"], giveaway["ends_at"],
                giveaway["winners_count"], giveaway["entries"],
                ended=True, winners=winners,
            )
            await message.edit(embed=embed, view=None)

            if winners:
                winner_mentions = " ".join(f"<@{w}>" for w in winners)
                await channel.send(
                    f"🎉 Congratulations {winner_mentions}! You won **{giveaway['prize']}**!"
                )
            else:
                await channel.send("No valid entries for this giveaway — no winners.")

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ── /gcreate ──────────────────────────────────────────────────────────
    @app_commands.command(name="gcreate", description="Create a giveaway.")
    @app_commands.describe(
        prize="What are you giving away?",
        duration="Duration e.g. 1d, 2h30m, 45m",
        winners="Number of winners",
        required_role="Role required to enter",
        min_level="Minimum level required to enter",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def gcreate(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: str,
        winners: int = 1,
        required_role: discord.Role = None,
        min_level: int = 0,
    ):
        ends_at = parse_duration(duration)
        if not ends_at:
            await interaction.response.send_message(
                "Invalid duration! Use formats like `1d`, `2h`, `30m`, `1h30m`.", ephemeral=True
            )
            return

        view = GiveawayView()
        embed = giveaway_embed(prize, ends_at, winners, [])
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        await create_giveaway(
            self.db,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=message.id,
            prize=prize,
            winners_count=winners,
            ends_at=ends_at,
            required_role=required_role.id if required_role else None,
            min_level=min_level,
        )

    @gcreate.error
    async def gcreate_error(self, interaction, error):
        await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)

    # ── /gend ─────────────────────────────────────────────────────────────
    @app_commands.command(name="gend", description="End a giveaway early.")
    @app_commands.describe(message_id="The message ID of the giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def gend(self, interaction: discord.Interaction, message_id: str):
        giveaway = await self.db.giveaways.find_one({
            "message_id": message_id,
            "guild_id": str(interaction.guild.id),
            "ended": False,
        })
        if not giveaway:
            await interaction.response.send_message("Giveaway not found or already ended.", ephemeral=True)
            return

        await interaction.response.defer()
        channel = interaction.guild.get_channel(int(giveaway["channel_id"]))
        try:
            message = await channel.fetch_message(int(giveaway["message_id"]))
        except discord.NotFound:
            await interaction.followup.send("Original giveaway message not found.", ephemeral=True)
            return

        winners = await end_giveaway(self.db, giveaway, interaction.guild)
        embed = giveaway_embed(
            giveaway["prize"], giveaway["ends_at"],
            giveaway["winners_count"], giveaway["entries"],
            ended=True, winners=winners,
        )
        await message.edit(embed=embed, view=None)

        if winners:
            winner_mentions = " ".join(f"<@{w}>" for w in winners)
            await channel.send(f"🎉 Giveaway ended! Congratulations {winner_mentions}! Won: **{giveaway['prize']}**")
        else:
            await channel.send("Giveaway ended with no valid entries.")
        await interaction.followup.send("Giveaway ended.", ephemeral=True)

    # ── /greroll ──────────────────────────────────────────────────────────
    @app_commands.command(name="greroll", description="Re-roll a new winner from an ended giveaway.")
    @app_commands.describe(message_id="The message ID of the ended giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def greroll(self, interaction: discord.Interaction, message_id: str):
        giveaway = await self.db.giveaways.find_one({
            "message_id": message_id,
            "guild_id": str(interaction.guild.id),
            "ended": True,
        })
        if not giveaway:
            await interaction.response.send_message("Ended giveaway not found.", ephemeral=True)
            return

        member_roles: dict[str, list[str]] = {}
        for uid in giveaway["entries"]:
            member = interaction.guild.get_member(int(uid))
            if member:
                member_roles[uid] = [str(r.id) for r in member.roles]

        new_winners = pick_winners(giveaway, member_roles, count=1)
        if not new_winners:
            await interaction.response.send_message("No entries to re-roll from.", ephemeral=True)
            return

        winner_mention = f"<@{new_winners[0]}>"
        await interaction.response.send_message(
            f"🎉 Re-rolled! New winner: {winner_mention} — **{giveaway['prize']}**!"
        )

    # ── /glist ────────────────────────────────────────────────────────────
    @app_commands.command(name="glist", description="List all active giveaways.")
    async def glist(self, interaction: discord.Interaction):
        cursor = self.db.giveaways.find({
            "guild_id": str(interaction.guild.id),
            "ended": False,
        })
        active = await cursor.to_list(length=20)
        if not active:
            await interaction.response.send_message("No active giveaways right now.", ephemeral=True)
            return

        embed = discord.Embed(title="🎉 Active Giveaways", color=discord.Color.green())
        for g in active:
            channel = interaction.guild.get_channel(int(g["channel_id"]))
            ch_mention = channel.mention if channel else "#unknown"
            embed.add_field(
                name=g["prize"],
                value=(
                    f"Channel: {ch_mention}\n"
                    f"Ends: <t:{int(g['ends_at'].timestamp())}:R>\n"
                    f"Entries: {len(g['entries'])} | Winners: {g['winners_count']}\n"
                    f"Message ID: `{g['message_id']}`"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    bot.add_view(GiveawayView())  # Persistent view — survives restarts
    await bot.add_cog(Giveaways(bot))
