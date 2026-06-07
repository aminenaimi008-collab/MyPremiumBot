import discord
from discord.ext import commands
import time
import config
from bot.database import db
from bot.utils.helpers import embed, error_embed, success_embed, has_permissions


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        await member.kick(reason=reason)
        await ctx.send(embed=success_embed(f"✅ {member} has been kicked. Reason: {reason}"))

    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="No reason provided"):
        await member.ban(reason=reason)
        await ctx.send(embed=success_embed(f"✅ {member} has been banned. Reason: {reason}"))

    @commands.hybrid_command(name="unban", description="Unban a member")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, *, member):
        banned_users = [entry async for entry in ctx.guild.bans()]
        name, discriminator = member.split("#") if "#" in member else (member, None)
        for ban_entry in banned_users:
            user = ban_entry.user
            if (user.name, user.discriminator) == (name, discriminator) or str(user.id) == member:
                await ctx.guild.unban(user)
                await ctx.send(embed=success_embed(f"✅ {user} has been unbanned."))
                return
        await ctx.send(embed=error_embed("❌ User not found in ban list."))

    @commands.hybrid_command(name="timeout", description="Timeout a member")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
        duration = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(embed=success_embed(f"✅ {member} has been timed out for {minutes} minutes. Reason: {reason}"))

    @commands.hybrid_command(name="untimeout", description="Remove timeout from a member")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member):
        await member.timeout(None)
        await ctx.send(embed=success_embed(f"✅ {member}'s timeout has been removed."))

    @commands.hybrid_command(name="warn", description="Warn a member")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="No reason provided"):
        await db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            [ctx.guild.id, member.id, ctx.author.id, reason, time.time()],
        )
        await ctx.send(embed=success_embed(f"✅ {member} has been warned. Reason: {reason}"))

    @commands.hybrid_command(name="warnings", description="View warnings for a member")
    @commands.has_permissions(moderate_members=True)
    async def warnings(self, ctx, member: discord.Member):
        rows = await db.fetchall(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 10",
            [ctx.guild.id, member.id],
        )
        if not rows:
            await ctx.send(embed=error_embed(f"❌ {member} has no warnings."))
            return
        e = embed(title=f"Warnings for {member}", description=f"Total: {len(rows)}", color=config.EMBED_COLOR)
        for row in rows[:5]:
            mod = ctx.guild.get_member(row["moderator_id"])
            e.add_field(
                name=f"#{row['id']} - {row['reason'][:50]}",
                value=f"Mod: {mod.mention if mod else 'Unknown'}\n<t:{int(row['timestamp'])}:R>",
                inline=False,
            )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="clearwarn", description="Clear all warnings for a member")
    @commands.has_permissions(moderate_members=True)
    async def clearwarn(self, ctx, member: discord.Member):
        await db.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", [ctx.guild.id, member.id])
        await ctx.send(embed=success_embed(f"✅ Warnings cleared for {member}."))

    @commands.hybrid_command(name="purge", description="Delete messages in bulk")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        if amount < 1 or amount > 100:
            await ctx.send(embed=error_embed("❌ Amount must be between 1-100."))
            return
        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(embed=success_embed(f"✅ Deleted {len(deleted) - 1} messages."))
        await msg.delete(delay=3)

    @commands.hybrid_command(name="nuke", description="Clone and delete a channel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        new_channel = await ctx.channel.clone()
        await ctx.channel.delete()
        msg = await new_channel.send(embed=success_embed("💣 Channel has been nuked!"))
        await msg.delete(delay=3)

    @commands.hybrid_command(name="lock", description="Lock a channel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(embed=success_embed(f"🔒 {channel.mention} has been locked."))

    @commands.hybrid_command(name="unlock", description="Unlock a channel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(embed=success_embed(f"🔓 {channel.mention} has been unlocked."))

    @commands.hybrid_command(name="say", description="Make the bot say something")
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx, *, message):
        await ctx.message.delete()
        await ctx.send(message)

    @commands.hybrid_command(name="slowmode", description="Set slowmode in a channel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(embed=success_embed(f"🐢 Slowmode set to {seconds}s in {ctx.channel.mention}"))

    @commands.hybrid_command(name="modstats", description="View moderation stats")
    @commands.has_permissions(moderate_members=True)
    async def modstats(self, ctx):
        total_warns = await db.fetchone(
            "SELECT COUNT(*) as count FROM warnings WHERE guild_id = ?", [ctx.guild.id]
        )
        total_bans = len([entry async for entry in ctx.guild.bans()])
        e = embed(
            title=f"📊 Mod Stats - {ctx.guild.name}",
            fields=[
                ("Total Warnings", total_warns["count"], True),
                ("Total Bans", total_bans, True),
                ("Total Members", ctx.guild.member_count, True),
            ],
        )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="setup", description="Setup moderation channels")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        mod_log = discord.utils.get(ctx.guild.channels, name=config.MOD_LOG_CHANNEL)
        if not mod_log:
            mod_log = await ctx.guild.create_text_channel(config.MOD_LOG_CHANNEL)
            await mod_log.set_permissions(ctx.guild.default_role, view_channel=False)

        await db.execute(
            "INSERT OR REPLACE INTO guild_config (guild_id, mod_log_channel) VALUES (?, ?)",
            [ctx.guild.id, mod_log.id],
        )
        await ctx.send(embed=success_embed(f"✅ Setup complete! Mod log: {mod_log.mention}"))


async def setup(bot):
    await bot.add_cog(Moderation(bot))
