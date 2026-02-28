# Discord Community Bot

A fully modular, scalable Discord bot built with **Python**, **discord.py 2.x**, and **MongoDB**.

## Features
- ⭐ Leveling System (XP, ranks, level roles)
- 💰 Economy System (balance, shop, daily, work)
- 🎉 Giveaway System (timed, button-based, weighted entries)
- 🎫 Ticket System (private channels, transcripts)
- 🔨 Moderation (warn, kick, ban, mute, auto-mod, logging)
- 🏷️ Auto Roles (join role, level roles, button panel, temporary roles)
- 🔧 Utility (/ping, /uptime, /botinfo, /help)

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure your secrets
Copy `.env.example` to `.env` and fill in your values:
```
BOT_TOKEN=your_discord_bot_token
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/discord_bot
```

### 3. Configure the bot
Open `config.py` and adjust:
- XP rates, cooldowns, ignored channels
- Economy rates and currency name
- Channel IDs for logging
- Role IDs for auto-assign and level rewards
- Enable/disable any system

### 4. Run the bot
```bash
python bot.py
```

---

## Discord Developer Portal Setup

1. Go to https://discord.com/developers/applications
2. Create a new application → Bot → Add Bot
3. Copy your token → paste into `.env`
4. Enable **Server Members Intent** and **Message Content Intent** under Privileged Intents
5. Invite your bot with scopes: `bot` + `applications.commands`
6. Required permissions: Manage Roles, Manage Channels, Kick Members, Ban Members, Manage Messages, Moderate Members, Read Message History, Send Messages, Embed Links, Attach Files

---

## Project Structure

```
discord_bot/
├── bot.py               # Entry point
├── config.py            # All configuration
├── requirements.txt
├── .env                 # Your secrets (never commit this!)
├── commands/            # Slash command cogs
│   ├── leveling.py
│   ├── economy.py
│   ├── giveaways.py
│   ├── tickets.py
│   ├── moderation.py
│   ├── autoroles.py
│   └── utility.py
├── events/              # Discord event listeners
│   ├── on_message.py
│   ├── on_member_join.py
│   ├── on_member_remove.py
│   └── on_message_edit.py
├── services/            # Business logic
│   ├── xp_service.py
│   ├── economy_service.py
│   ├── moderation_service.py
│   ├── giveaway_service.py
│   └── ticket_service.py
└── models/              # MongoDB helpers
    └── user_model.py
```

---

## Adding Shop Items

Shop items are stored per-guild in MongoDB. Add to your guild document:
```json
{
  "guild_id": "YOUR_GUILD_ID",
  "shop_items": [
    {
      "id": "vip_30d",
      "name": "VIP Role (30 days)",
      "description": "Unlock VIP perks for 30 days!",
      "price": 5000,
      "type": "role",
      "role_id": "ROLE_ID_HERE",
      "duration_hours": 720
    }
  ]
}
```

## Adding Role Panel Buttons

Add to your guild document:
```json
{
  "role_panel": [
    {"label": "Gamer", "role_id": "ROLE_ID", "emoji": "🎮"},
    {"label": "Artist", "role_id": "ROLE_ID", "emoji": "🎨"}
  ]
}
```

---

## Deployment (Railway)

1. Push code to GitHub (make sure `.env` is in `.gitignore`)
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Add environment variables: `BOT_TOKEN` and `MONGO_URI`
4. Railway auto-detects Python and starts the bot

---

## Common Issues

| Problem | Solution |
|---------|----------|
| Slash commands not showing | Wait up to 1 hour for global sync, or use guild sync for testing |
| Bot can't assign roles | Move bot's role above target roles in Server Settings → Roles |
| XP not being granted | Check that Message Content Intent is enabled in Dev Portal |
| MongoDB connection error | Check your MONGO_URI and that your IP is whitelisted in Atlas |
