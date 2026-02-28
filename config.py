# config.py — Central configuration for the Discord bot
# Edit values here to customize your bot without touching any other files.

import os
from dotenv import load_dotenv

load_dotenv()

# ── Secrets (loaded from .env) ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# ── Leveling ───────────────────────────────────────────────────────────────
XP_MIN_PER_MESSAGE = 15     # Minimum XP granted per message
XP_MAX_PER_MESSAGE = 25     # Maximum XP granted per message
XP_COOLDOWN_SECONDS = 60     # Seconds a user must wait before earning XP again
XP_IGNORED_CHANNELS = []     # List of channel IDs where XP is NOT granted

# Level → Role ID mapping.  Add as many levels as you want.
# Example: {5: 111222333444555666, 10: 222333444555666777}
LEVEL_ROLES: dict[int, int] = {}

STACK_LEVEL_ROLES = True       # True = keep all previous level roles
# False = remove old role when new one is assigned
# Channel ID for level-up messages. None = DM the user.
LEVEL_UP_CHANNEL = None

# ── Economy ────────────────────────────────────────────────────────────────
DAILY_AMOUNT = 500    # Coins rewarded by /daily
DAILY_COOLDOWN = 86400  # Seconds between /daily uses (86400 = 24 hours)
WORK_MIN = 50     # Minimum coins from /work
WORK_MAX = 200    # Maximum coins from /work
WORK_COOLDOWN = 3600   # Seconds between /work uses (3600 = 1 hour)
CHAT_COINS_MIN = 1      # Minimum coins earned per chat message
CHAT_COINS_MAX = 5      # Maximum coins earned per chat message
MAX_DAILY_CHAT_COINS = 500    # Maximum coins a user can earn from chat per day
CURRENCY_NAME = "coins"
CURRENCY_SYMBOL = "🪙"

# ── Moderation ─────────────────────────────────────────────────────────────
MOD_LOG_CHANNEL = 1477311063631466638      # Channel ID for moderation logs
JOIN_LOG_CHANNEL = 1477311096661606474      # Channel ID for join/leave logs
# Channel ID for message edit/delete logs
MSG_LOG_CHANNEL = 1477311117633257503
BLACKLISTED_WORDS = ["fuck", "fucking", "motherfucker", "mf", "shit", "bullshit", "bitch", "bitches", "asshole", "dick", "pussy", "bastard", "slut", "whore", "cunt", "nigger", "nigga", "faggot", "retard", "kike", "chink", "paki", "porn", "porno", "hentai", "nudes", "onlyfans", "sex", "sexy", "blowjob", "handjob", "cum", "dickpic", "boobs", "tits", "kys", "kill yourself", "go die", "hang yourself", "cut yourself", "loser", "noob", "dogshit", "trash", "stupid", "idiot"]        # List of words to auto-delete
ANTI_LINK_ENABLED = True      # Delete links posted by non-staff users
ANTI_SPAM_THRESHOLD = 5        # Messages within 5 seconds = spam
STAFF_ROLE_IDS = [1477310091605835869]        # Role IDs that bypass auto-mod

# ── Tickets ────────────────────────────────────────────────────────────────
# Category ID where ticket channels are created
TICKET_CATEGORY_ID = 1477311539911594145
# Role ID pinged when a ticket is opened
TICKET_STAFF_ROLE = 1477311787182456872
# Channel where transcripts are sent on close
TICKET_LOG_CHANNEL = 1477324891664679016

# ── Giveaways ──────────────────────────────────────────────────────────────
GIVEAWAY_EMOJI = "🎉"

# ── Auto Roles ─────────────────────────────────────────────────────────────
# Role ID given to every new member on join
AUTO_JOIN_ROLE = 1477310129245520005

# ── System Toggles ─────────────────────────────────────────────────────────
LEVELING_ENABLED = True
ECONOMY_ENABLED = True
GIVEAWAYS_ENABLED = True
TICKETS_ENABLED = True
MODERATION_ENABLED = True
AUTOROLES_ENABLED = True
