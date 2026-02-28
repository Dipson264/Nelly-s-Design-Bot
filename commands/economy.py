# commands/economy.py — /balance, /daily, /work, /deposit, /withdraw, /pay,
#                       /shop, /buy, /inventory, and admin economy commands.

import discord
from discord import app_commands
from discord.ext import commands

import config
from models.user_model import get_or_create_user
from services import economy_service as eco


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /balance ──────────────────────────────────────────────────────────
    @app_commands.command(name="balance", description="Check your coin balance.")
    @app_commands.describe(member="Member to check (leave empty for yourself)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        bal = await eco.get_balance(self.db, target.id, interaction.guild.id)
        embed = discord.Embed(title=f"{config.CURRENCY_SYMBOL} {target.display_name}'s Balance", color=discord.Color.green())
        embed.add_field(name="Wallet", value=f"{config.CURRENCY_SYMBOL} {bal['balance']:,}", inline=True)
        embed.add_field(name="Bank",   value=f"{config.CURRENCY_SYMBOL} {bal['bank']:,}", inline=True)
        embed.add_field(name="Total",  value=f"{config.CURRENCY_SYMBOL} {bal['balance'] + bal['bank']:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /daily ────────────────────────────────────────────────────────────
    @app_commands.command(name="daily", description="Claim your daily coins.")
    async def daily(self, interaction: discord.Interaction):
        success, msg, _ = await eco.claim_daily(self.db, interaction.user.id, interaction.guild.id)
        color = discord.Color.green() if success else discord.Color.red()
        await interaction.response.send_message(
            embed=discord.Embed(description=msg, color=color)
        )

    # ── /work ─────────────────────────────────────────────────────────────
    @app_commands.command(name="work", description="Work to earn coins.")
    async def work(self, interaction: discord.Interaction):
        success, msg, _ = await eco.do_work(self.db, interaction.user.id, interaction.guild.id)
        color = discord.Color.green() if success else discord.Color.red()
        await interaction.response.send_message(
            embed=discord.Embed(description=msg, color=color)
        )

    # ── /deposit ──────────────────────────────────────────────────────────
    @app_commands.command(name="deposit", description="Deposit coins into your bank.")
    @app_commands.describe(amount="Amount to deposit")
    async def deposit(self, interaction: discord.Interaction, amount: int):
        success, msg = await eco.deposit(self.db, interaction.user.id, interaction.guild.id, amount)
        color = discord.Color.green() if success else discord.Color.red()
        await interaction.response.send_message(
            embed=discord.Embed(description=msg, color=color)
        )

    # ── /withdraw ─────────────────────────────────────────────────────────
    @app_commands.command(name="withdraw", description="Withdraw coins from your bank.")
    @app_commands.describe(amount="Amount to withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: int):
        success, msg = await eco.withdraw(self.db, interaction.user.id, interaction.guild.id, amount)
        color = discord.Color.green() if success else discord.Color.red()
        await interaction.response.send_message(
            embed=discord.Embed(description=msg, color=color)
        )

    # ── /pay ──────────────────────────────────────────────────────────────
    @app_commands.command(name="pay", description="Send coins to another member.")
    @app_commands.describe(member="Who to pay", amount="Amount to send")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't pay yourself!", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("You can't pay bots!", ephemeral=True)
            return
        success, msg = await eco.pay(self.db, interaction.user.id, member.id, interaction.guild.id, amount)
        color = discord.Color.green() if success else discord.Color.red()
        if success:
            msg = f"Sent {config.CURRENCY_SYMBOL} **{amount}** to {member.mention}!"
        await interaction.response.send_message(embed=discord.Embed(description=msg, color=color))

    # ── /baltop ───────────────────────────────────────────────────────────
    @app_commands.command(name="baltop", description="Show the richest members.")
    async def baltop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cursor = self.db.users.find(
            {"guild_id": str(interaction.guild.id)},
            sort=[("balance", -1)],
            limit=10,
        )
        top = await cursor.to_list(length=10)
        if not top:
            await interaction.followup.send("No economy data yet!")
            return
        embed = discord.Embed(title=f"{config.CURRENCY_SYMBOL} Richest Members", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, doc in enumerate(top):
            member = interaction.guild.get_member(int(doc["user_id"]))
            name = member.display_name if member else f"User {doc['user_id']}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{medal} **{name}** — {config.CURRENCY_SYMBOL} {doc['balance']:,}")
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)

    # ── /shop ─────────────────────────────────────────────────────────────
    @app_commands.command(name="shop", description="Browse the server shop.")
    async def shop(self, interaction: discord.Interaction):
        items = await eco.get_shop(self.db, interaction.guild.id)
        if not items:
            await interaction.response.send_message(
                "The shop is empty! An admin can add items to the guild document in MongoDB.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(title="🛒 Server Shop", color=discord.Color.blurple())
        for item in items:
            duration = f" ({item['duration_hours']}h)" if item.get("duration_hours") else " (permanent)"
            embed.add_field(
                name=f"{item['name']} — {config.CURRENCY_SYMBOL} {item['price']:,}",
                value=f"{item.get('description', 'No description')}{duration}\nID: `{item['id']}`",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    # ── /buy ──────────────────────────────────────────────────────────────
    @app_commands.command(name="buy", description="Buy an item from the shop.")
    @app_commands.describe(item_id="The item ID shown in /shop")
    async def buy(self, interaction: discord.Interaction, item_id: str):
        success, result = await eco.buy_item(self.db, interaction.user.id, interaction.guild.id, item_id)
        if not success:
            await interaction.response.send_message(result, ephemeral=True)
            return

        item = result
        # Apply role if applicable
        if item["type"] == "role" and item.get("role_id"):
            role = interaction.guild.get_role(int(item["role_id"]))
            if role:
                try:
                    await interaction.user.add_roles(role, reason=f"Purchased {item['name']}")
                except discord.Forbidden:
                    pass

        embed = discord.Embed(
            description=f"✅ You bought **{item['name']}**!",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    # ── /inventory ────────────────────────────────────────────────────────
    @app_commands.command(name="inventory", description="View your inventory.")
    async def inventory(self, interaction: discord.Interaction):
        user = await get_or_create_user(self.db, interaction.user.id, interaction.guild.id)
        inv = user.get("inventory", [])
        if not inv:
            await interaction.response.send_message("Your inventory is empty.", ephemeral=True)
            return
        embed = discord.Embed(title="🎒 Your Inventory", color=discord.Color.blurple())
        for item in inv:
            exp = item.get("expires")
            exp_str = f" (expires <t:{int(exp.timestamp())}:R>)" if exp else " (permanent)"
            embed.add_field(name=item["name"], value=f"Type: {item['type']}{exp_str}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Admin: /addcoins ──────────────────────────────────────────────────
    @app_commands.command(name="addcoins", description="[Admin] Add coins to a member.")
    @app_commands.describe(member="Target member", amount="Amount to add")
    @is_admin()
    async def addcoins(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await eco.add_coins(self.db, member.id, interaction.guild.id, amount)
        await interaction.response.send_message(
            f"Added {config.CURRENCY_SYMBOL} **{amount}** to {member.mention}.", ephemeral=True
        )

    @addcoins.error
    async def addcoins_error(self, interaction, error):
        await interaction.response.send_message("You need to be an administrator.", ephemeral=True)

    # ── Admin: /removecoins ───────────────────────────────────────────────
    @app_commands.command(name="removecoins", description="[Admin] Remove coins from a member.")
    @app_commands.describe(member="Target member", amount="Amount to remove")
    @is_admin()
    async def removecoins(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await eco.remove_coins(self.db, member.id, interaction.guild.id, amount)
        await interaction.response.send_message(
            f"Removed {config.CURRENCY_SYMBOL} **{amount}** from {member.mention}.", ephemeral=True
        )

    @removecoins.error
    async def removecoins_error(self, interaction, error):
        await interaction.response.send_message("You need to be an administrator.", ephemeral=True)

    # ── Admin: /setcoins ──────────────────────────────────────────────────
    @app_commands.command(name="setcoins", description="[Admin] Set a member's wallet balance.")
    @app_commands.describe(member="Target member", amount="New balance")
    @is_admin()
    async def setcoins(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await eco.set_coins(self.db, member.id, interaction.guild.id, amount)
        await interaction.response.send_message(
            f"Set {member.mention}'s balance to {config.CURRENCY_SYMBOL} **{amount}**.", ephemeral=True
        )

    @setcoins.error
    async def setcoins_error(self, interaction, error):
        await interaction.response.send_message("You need to be an administrator.", ephemeral=True)

    # ── Admin: /reseteconomy ──────────────────────────────────────────────
    @app_commands.command(name="reseteconomy", description="[Admin] Reset a member's economy data.")
    @app_commands.describe(member="Target member")
    @is_admin()
    async def reseteconomy(self, interaction: discord.Interaction, member: discord.Member):
        await self.db.users.update_one(
            {"user_id": str(member.id), "guild_id": str(interaction.guild.id)},
            {"$set": {"balance": 0, "bank": 0, "inventory": [], "last_daily": None, "last_work": None}},
        )
        await interaction.response.send_message(
            f"Reset {member.mention}'s economy data.", ephemeral=True
        )

    @reseteconomy.error
    async def reseteconomy_error(self, interaction, error):
        await interaction.response.send_message("You need to be an administrator.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))
