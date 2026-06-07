import asyncio
import config
from bot.client import Bot

bot = Bot()

if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set in .env file")
        exit(1)
    asyncio.run(bot.start(config.DISCORD_TOKEN))
