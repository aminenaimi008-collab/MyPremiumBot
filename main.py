import asyncio
import sys
import config
from bot.client import Bot

bot = Bot()

if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set", flush=True)
        sys.exit(1)
    try:
        asyncio.run(bot.start(config.DISCORD_TOKEN))
    except KeyboardInterrupt:
        pass
