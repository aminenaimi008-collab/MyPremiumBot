import discord
from discord.ext import commands
import config
from bot.database import db


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            owner_id=config.OWNER_ID,
        )

    async def setup_hook(self):
        await db.connect()
        await self.load_cog("bot.cogs.moderation")
        await self.load_cog("bot.cogs.tickets")
        await self.load_cog("bot.cogs.giveaways")
        await self.load_cog("bot.cogs.economy")
        await self.load_cog("bot.cogs.premium")
        await self.load_cog("bot.cogs.music")
        await self.tree.sync()

    async def load_cog(self, cog_path):
        try:
            await self.load_extension(cog_path)
            print(f"Loaded: {cog_path}")
        except Exception as e:
            print(f"Failed to load {cog_path}: {e}")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Invite URL: {discord.utils.oauth_url(self.user.id, permissions=discord.Permissions(8))}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | !help",
            )
        )

    async def on_guild_join(self, guild):
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | !help",
            )
        )

    async def get_guild_prefix(self, guild):
        return "!"

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.NotOwner):
            await ctx.send("❌ This command is owner-only.", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ Command on cooldown. Try again in {error.retry_after:.0f}s.", ephemeral=True)
        elif isinstance(error, commands.CommandNotFound):
            return
        else:
            await ctx.send(f"❌ An error occurred: {error}", ephemeral=True)
            print(f"Error: {error}")
