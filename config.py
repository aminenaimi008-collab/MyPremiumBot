import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", "0"))

EMBED_COLOR = 0x5865F2
ERROR_COLOR = 0xED4245
SUCCESS_COLOR = 0x57F287
PREMIUM_COLOR = 0xFEE75C

TICKET_CATEGORY_NAME = "🎫 Tickets"
TICKET_LOG_CHANNEL = "ticket-logs"
MOD_LOG_CHANNEL = "mod-logs"
