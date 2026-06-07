import asyncio
import os
import config
from bot.client import Bot

bot = Bot()

async def run_bot():
    if not config.DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set")
        exit(1)
    await bot.start(config.DISCORD_TOKEN)

async def run_health():
    from aiohttp import web
    app = web.Application()
    async def health(request):
        return web.Response(text="OK")
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await asyncio.gather(run_bot(), run_health())

if __name__ == "__main__":
    asyncio.run(main())
