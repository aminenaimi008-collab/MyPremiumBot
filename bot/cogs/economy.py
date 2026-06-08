import discord
from discord.ext import commands
import time
import math
import random
import config
from bot.database import db
from bot.utils.helpers import embed, error_embed, success_embed, is_premium

XP_PER_MESSAGE = random.randint(10, 25)
XP_COOLDOWN = 60
BASE_XP_REQUIRED = 100
XP_SCALE = 1.5


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldowns = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        now = time.time()

        cooldown_key = f"{guild_id}_{user_id}"
        last_xp = self.xp_cooldowns.get(cooldown_key, 0)
        if now - last_xp < XP_COOLDOWN:
            return
        self.xp_cooldowns[cooldown_key] = now

        row = await db.fetchone(
            "SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id],
        )
        if row:
            current_xp = row["xp"]
            current_level = row["level"]
        else:
            current_xp = 0
            current_level = 1

        xp_to_add = random.randint(10, 25)
        current_xp += xp_to_add

        required = int(BASE_XP_REQUIRED * (current_level ** XP_SCALE))
        new_level = current_level
        leveled_up = False
        while current_xp >= required:
            current_xp -= required
            new_level += 1
            required = int(BASE_XP_REQUIRED * (new_level ** XP_SCALE))
            leveled_up = True

        await db.execute(
            "INSERT OR REPLACE INTO levels (user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)",
            [user_id, guild_id, current_xp, new_level],
        )

        if leveled_up:
            try:
                await message.channel.send(
                    embed=success_embed(f"🎉 {message.author.mention} leveled up to **Level {new_level}**!")
                )
            except:
                pass

        coin_chance = random.random()
        if coin_chance < 0.3:
            coins = random.randint(1, 10)
            econ_row = await db.fetchone(
                "SELECT balance FROM economy WHERE user_id = ? AND guild_id = ?",
                [user_id, guild_id],
            )
            current_balance = econ_row["balance"] if econ_row else 0
            await db.execute(
                "INSERT OR REPLACE INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)",
                [user_id, guild_id, current_balance + coins],
            )

    @commands.hybrid_command(name="rank", description="Check your rank or someone else's")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        row = await db.fetchone(
            "SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?",
            [member.id, ctx.guild.id],
        )
        if not row:
            await ctx.send(embed=error_embed(f"❌ {member.display_name} has no XP yet."))
            return

        required = int(BASE_XP_REQUIRED * (row["level"] ** XP_SCALE))
        all_rows = await db.fetchall(
            "SELECT user_id, level FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC",
            [ctx.guild.id],
        )
        rank = 1
        for r in all_rows:
            if r["user_id"] == member.id:
                break
            rank += 1

        e = embed(
            title=f"📊 {member.display_name}'s Rank",
            color=member.color if member.color.value else config.EMBED_COLOR,
            fields=[
                ("Level", str(row["level"]), True),
                ("XP", f"{row['xp']}/{required}", True),
                ("Rank", f"#{rank}", True),
                ("Progress", f"{row['xp'] / required * 100:.1f}%", True),
            ],
            thumbnail=member.display_avatar.url,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="leaderboard", description="Show the server leaderboard")
    async def leaderboard(self, ctx):
        rows = await db.fetchall(
            "SELECT user_id, level, xp FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
            [ctx.guild.id],
        )
        if not rows:
            await ctx.send(embed=error_embed("❌ No data yet."))
            return

        desc = []
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            user = ctx.guild.get_member(row["user_id"])
            name = user.display_name if user else f"Unknown ({row['user_id']})"
            medal = medals[i] if i < 3 else f"#{i + 1}"
            desc.append(f"{medal} **{name}** — Level {row['level']} ({row['xp']} XP)")

        e = embed(title=f"🏆 Leaderboard - {ctx.guild.name}", description="\n".join(desc))
        await ctx.send(embed=e)

    @commands.hybrid_command(name="balance", description="Check your coin balance")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        row = await db.fetchone(
            "SELECT balance FROM economy WHERE user_id = ? AND guild_id = ?",
            [member.id, ctx.guild.id],
        )
        balance = row["balance"] if row else 0
        e = embed(
            title=f"💰 {member.display_name}'s Balance",
            description=f"**{balance:,} coins**",
            color=config.EMBED_COLOR,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="daily", description="Claim your daily reward")
    async def daily(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild.id
        now = time.time()

        row = await db.fetchone(
            "SELECT last_claim, streak FROM daily_rewards WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id],
        )

        if row:
            last_claim = row["last_claim"]
            streak = row["streak"]
            if now - last_claim < 86400:
                remaining = 86400 - (now - last_claim)
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                await ctx.send(embed=error_embed(f"❌ You can claim again in {hours}h {minutes}m."))
                return

            if now - last_claim < 172800:
                streak += 1
            else:
                streak = 1
        else:
            streak = 1

        bonus = min(streak * 10, 100)
        coins = 50 + bonus
        if await is_premium(ctx.guild.id):
            coins *= 2

        econ_row = await db.fetchone(
            "SELECT balance FROM economy WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id],
        )
        current_balance = econ_row["balance"] if econ_row else 0

        await db.execute(
            "INSERT OR REPLACE INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)",
            [user_id, guild_id, current_balance + coins],
        )
        await db.execute(
            "INSERT OR REPLACE INTO daily_rewards (user_id, guild_id, last_claim, streak) VALUES (?, ?, ?, ?)",
            [user_id, guild_id, now, streak],
        )

        e = success_embed(f"✅ You claimed **{coins:,} coins**! (Streak: {streak} days)")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="transfer", description="Transfer coins to another user")
    async def transfer(self, ctx, member: discord.Member, amount: int):
        if amount < 1:
            await ctx.send(embed=error_embed("❌ Amount must be positive."))
            return

        sender = await db.fetchone(
            "SELECT balance FROM economy WHERE user_id = ? AND guild_id = ?",
            [ctx.author.id, ctx.guild.id],
        )
        sender_balance = sender["balance"] if sender else 0

        if sender_balance < amount:
            await ctx.send(embed=error_embed(f"❌ Insufficient coins. You have {sender_balance:,}."))
            return

        receiver = await db.fetchone(
            "SELECT balance FROM economy WHERE user_id = ? AND guild_id = ?",
            [member.id, ctx.guild.id],
        )
        receiver_balance = receiver["balance"] if receiver else 0

        await db.execute(
            "INSERT OR REPLACE INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)",
            [ctx.author.id, ctx.guild.id, sender_balance - amount],
        )
        await db.execute(
            "INSERT OR REPLACE INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)",
            [member.id, ctx.guild.id, receiver_balance + amount],
        )

        await ctx.send(embed=success_embed(f"✅ Transferred **{amount:,} coins** to {member.mention}."))

    @commands.hybrid_command(name="shop", description="View the server shop")
    async def shop(self, ctx):
        e = embed(
            title="🛒 Shop",
            description="More items coming soon with Premium!",
            fields=[
                ("Premium Role", "500 coins — Buy a premium role!", False),
            ],
        )
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Economy(bot))
