# services/ticket_service.py — Ticket creation, closing, and transcript export.

from datetime import datetime

import discord

import config


async def create_ticket(db, guild: discord.Guild, user: discord.Member) -> tuple[discord.TextChannel | None, str | None]:
    """Create a ticket channel. Returns (channel, error_message)."""
    # Check for existing open ticket
    existing = await db.tickets.find_one({
        "user_id": str(user.id),
        "guild_id": str(guild.id),
        "status": "open",
    })
    if existing:
        ch = guild.get_channel(int(existing["channel_id"]))
        return None, f"You already have an open ticket: {ch.mention if ch else '#deleted-channel'}."

    # Resolve category
    category = None
    if config.TICKET_CATEGORY_ID:
        category = guild.get_channel(int(config.TICKET_CATEGORY_ID))

    # Build permission overwrites
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(
            read_messages=True, send_messages=True, attach_files=True, embed_links=True
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_channels=True, manage_messages=True
        ),
    }
    if config.TICKET_STAFF_ROLE:
        staff_role = guild.get_role(int(config.TICKET_STAFF_ROLE))
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            )

    try:
        channel = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            overwrites=overwrites,
            category=category,
            topic=f"Support ticket for {user} (ID: {user.id})",
        )
    except discord.Forbidden:
        return None, "I don't have permission to create channels."

    # Save to DB
    await db.tickets.insert_one({
        "guild_id": str(guild.id),
        "user_id": str(user.id),
        "channel_id": str(channel.id),
        "status": "open",
        "created_at": datetime.utcnow(),
        "closed_at": None,
        "transcript": [],
    })

    # Welcome embed
    embed = discord.Embed(
        title="🎫 Support Ticket",
        description=(
            f"Hello {user.mention}! A staff member will be with you shortly.\n\n"
            "Please describe your issue in detail.\n"
            "Use `/close` to close this ticket when you're done."
        ),
        color=discord.Color.blue(),
        timestamp=datetime.utcnow(),
    )

    close_btn = discord.ui.Button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    view = discord.ui.View(timeout=None)
    view.add_item(close_btn)

    staff_ping = ""
    if config.TICKET_STAFF_ROLE:
        staff_role = guild.get_role(int(config.TICKET_STAFF_ROLE))
        if staff_role:
            staff_ping = staff_role.mention

    await channel.send(content=staff_ping, embed=embed, view=view)
    return channel, None


async def close_ticket(db, channel: discord.TextChannel, closer: discord.Member) -> str:
    """Close a ticket: export transcript, archive channel, update DB."""
    ticket = await db.tickets.find_one({
        "channel_id": str(channel.id),
        "status": "open",
    })
    if not ticket:
        return "No open ticket found for this channel."

    # Build transcript
    messages = []
    async for msg in channel.history(limit=500, oldest_first=True):
        messages.append(
            f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{msg.author} ({msg.author.id}): {msg.content}"
        )

    transcript_text = "\n".join(messages)
    now = datetime.utcnow()

    await db.tickets.update_one(
        {"_id": ticket["_id"]},
        {"$set": {
            "status": "closed",
            "closed_at": now,
            "transcript": messages,
        }},
    )

    # Send transcript to log channel
    if config.TICKET_LOG_CHANNEL:
        log_ch = channel.guild.get_channel(int(config.TICKET_LOG_CHANNEL))
        if log_ch:
            guild = channel.guild
            opener = guild.get_member(int(ticket["user_id"]))
            embed = discord.Embed(
                title="🎫 Ticket Closed",
                color=discord.Color.red(),
                timestamp=now,
            )
            embed.add_field(name="Opened by", value=str(opener) if opener else ticket["user_id"])
            embed.add_field(name="Closed by", value=str(closer))
            embed.add_field(name="Duration", value=str(now - ticket["created_at"]).split(".")[0])

            file_content = transcript_text.encode("utf-8")
            file = discord.File(
                fp=__import__("io").BytesIO(file_content),
                filename=f"transcript-{channel.name}.txt",
            )
            await log_ch.send(embed=embed, file=file)

    # Delete the channel after a short delay
    await channel.send("Ticket closing in 5 seconds...")
    await __import__("asyncio").sleep(5)
    try:
        await channel.delete(reason=f"Ticket closed by {closer}")
    except discord.Forbidden:
        pass

    return "Ticket closed."
