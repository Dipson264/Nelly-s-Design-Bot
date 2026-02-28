# commands/autoroles.py — Button role panels, temporary role expiry task.

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config


class RolePanelView(discord.ui.View):
    """Dynamic role panel — reads roles from the guild document in MongoDB."""
    def __init__(self, roles: list[dict]):
        super().__init__(timeout=None)
        for role_data in roles[:25]:  # Discord limit: 25 buttons
            btn = discord.ui.Button(
                label=role_data["label"],
                style=discord.ButtonStyle.secondary,
                custom_id=f"role_toggle_{role_data['role_id']}",
                emoji=role_data.get("emoji"),
            )
            btn.callback = self.make_callback(role_data["role_id"])
            self.add_item(btn)

    def make_callback(self, role_id: str):
        async def callback(interaction: discord.Interaction):
            role = interaction.guild.get_role(int(role_id))
            if not role:
                await interaction.response.send_message("Role not found.", ephemeral=True)
                return
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Role panel self-remove")
                await interaction.response.send_message(f"❌ Removed **{role.name}**.", ephemeral=True)
            else:
                try:
                    await interaction.user.add_roles(role, reason="Role panel self-assign")
                    await interaction.response.send_message(f"✅ Added **{role.name}**.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("I couldn't assign that role (hierarchy issue).", ephemeral=True)
        return callback


class AutoRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.expire_roles_task.start()

    @property
    def db(self):
        return self.bot.db

    def cog_unload(self):
        self.expire_roles_task.cancel()

    # ── Background: expire temporary roles ────────────────────────────────
    @tasks.loop(minutes=1)
    async def expire_roles_task(self):
        now = datetime.utcnow()
        cursor = self.db.users.find({
            "inventory": {
                "$elemMatch": {
                    "expires": {"$lte": now},
                    "type": "role",
                }
            }
        })
        async for user_doc in cursor:
            guild = self.bot.get_guild(int(user_doc["guild_id"]))
            if not guild:
                continue
            member = guild.get_member(int(user_doc["user_id"]))
            expired_items = []
            kept_items = []
            for item in user_doc.get("inventory", []):
                exp = item.get("expires")
                if exp and exp <= now and item.get("type") == "role":
                    expired_items.append(item)
                else:
                    kept_items.append(item)

            for item in expired_items:
                if member and item.get("role_id"):
                    role = guild.get_role(int(item["role_id"]))
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Temporary role expired")
                        except discord.Forbidden:
                            pass

            if expired_items:
                await self.db.users.update_one(
                    {"_id": user_doc["_id"]},
                    {"$set": {"inventory": kept_items}},
                )

    @expire_roles_task.before_loop
    async def before_expire(self):
        await self.bot.wait_until_ready()

    # ── /rolepanel ────────────────────────────────────────────────────────
    @app_commands.command(name="rolepanel", description="[Admin] Post a self-assignable role panel.")
    @app_commands.describe(title="Panel title", description="Panel description")
    @app_commands.checks.has_permissions(administrator=True)
    async def rolepanel(self, interaction: discord.Interaction, title: str = "🎭 Role Selection",
                        description: str = "Click a button to assign or remove a role."):
        guild_doc = await self.db.guilds.find_one({"guild_id": str(interaction.guild.id)})
        role_panel = guild_doc.get("role_panel", []) if guild_doc else []

        if not role_panel:
            await interaction.response.send_message(
                "No role panel configured. Add a `role_panel` array to your guild document in MongoDB.\n"
                "Format: `[{\"label\": \"Gamer\", \"role_id\": \"123456\", \"emoji\": \"🎮\"}, ...]`",
                ephemeral=True,
            )
            return

        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        view = RolePanelView(role_panel)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Role panel posted!", ephemeral=True)

    @rolepanel.error
    async def rolepanel_error(self, interaction, error):
        await interaction.response.send_message("You need Administrator permission.", ephemeral=True)

    # ── /giverole ─────────────────────────────────────────────────────────
    @app_commands.command(name="giverole", description="[Admin] Give a (optionally temporary) role to a member.")
    @app_commands.describe(
        member="Target member",
        role="Role to give",
        duration="Optional duration e.g. 24h, 7d (leave blank for permanent)",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def giverole(self, interaction: discord.Interaction, member: discord.Member,
                       role: discord.Role, duration: str = None):
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message("I can't assign that role (hierarchy).", ephemeral=True)
            return

        await member.add_roles(role, reason=f"Assigned by {interaction.user}")

        expires = None
        if duration:
            from services.giveaway_service import parse_duration
            expires = parse_duration(duration)
            if not expires:
                await interaction.response.send_message("Invalid duration.", ephemeral=True)
                return

            inv_entry = {
                "item_id": f"role_{role.id}",
                "name": role.name,
                "type": "role",
                "role_id": str(role.id),
                "expires": expires,
            }
            await self.db.users.update_one(
                {"user_id": str(member.id), "guild_id": str(interaction.guild.id)},
                {"$push": {"inventory": inv_entry}},
                upsert=True,
            )

        exp_str = f" (expires <t:{int(expires.timestamp())}:R>)" if expires else " (permanent)"
        await interaction.response.send_message(
            f"✅ Gave **{role.name}** to {member.mention}{exp_str}.", ephemeral=True
        )

    @giverole.error
    async def giverole_error(self, interaction, error):
        await interaction.response.send_message("You need Manage Roles permission.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoRoles(bot))
