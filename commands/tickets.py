# commands/tickets.py — Ticket panel button, /close, persistent views.

import discord
from discord import app_commands
from discord.ext import commands

import config
from services.ticket_service import create_ticket, close_ticket


class TicketOpenView(discord.ui.View):
    """Persistent view — the 'Open Ticket' button stays active after restarts."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.blurple,
        emoji="🎫",
        custom_id="open_ticket",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        channel, error = await create_ticket(interaction.client.db, interaction.guild, interaction.user)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(f"✅ Your ticket has been created: {channel.mention}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    """Persistent 'Close Ticket' button inside ticket channels."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket",
    )
    async def close_ticket_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        result = await close_ticket(interaction.client.db, interaction.channel, interaction.user)
        if result != "Ticket closed.":
            await interaction.followup.send(result, ephemeral=True)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /ticketpanel ──────────────────────────────────────────────────────
    @app_commands.command(name="ticketpanel", description="[Admin] Post the ticket panel message.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticketpanel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description=(
                "Need help? Click the button below to open a private support ticket.\n\n"
                "A staff member will assist you as soon as possible."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="One ticket per user at a time.")
        await interaction.channel.send(embed=embed, view=TicketOpenView())
        await interaction.response.send_message("Ticket panel posted!", ephemeral=True)

    @ticketpanel.error
    async def ticketpanel_error(self, interaction, error):
        await interaction.response.send_message("You need Administrator permission.", ephemeral=True)

    # ── /close ────────────────────────────────────────────────────────────
    @app_commands.command(name="close", description="Close the current support ticket.")
    async def close(self, interaction: discord.Interaction):
        ticket = await self.db.tickets.find_one({
            "channel_id": str(interaction.channel.id),
            "status": "open",
        })
        if not ticket:
            await interaction.response.send_message(
                "This channel is not an open ticket.", ephemeral=True
            )
            return
        await interaction.response.defer()
        await close_ticket(self.db, interaction.channel, interaction.user)


async def setup(bot):
    # Register persistent views so buttons work after restart
    bot.add_view(TicketOpenView())
    bot.add_view(CloseTicketView())
    await bot.add_cog(Tickets(bot))
