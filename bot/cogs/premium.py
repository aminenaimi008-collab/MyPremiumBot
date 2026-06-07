import discord
from discord.ext import commands
import time
import secrets
import config
from bot.database import db
from bot.utils.helpers import embed, error_embed, success_embed, premium_embed


class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_premium(self, guild_id: int) -> bool:
        row = await db.fetchone(
            "SELECT premium_until FROM guild_config WHERE guild_id = ?", [guild_id],
        )
        if not row or row["premium_until"] == 0:
            return False
        return time.time() < row["premium_until"]

    @commands.hybrid_command(name="premium", description="Check premium status")
    async def premium_status(self, ctx):
        if await self.is_premium(ctx.guild.id):
            row = await db.fetchone(
                "SELECT premium_until FROM guild_config WHERE guild_id = ?", [ctx.guild.id],
            )
            remaining = int(row["premium_until"] - time.time())
            days = remaining // 86400
            hours = (remaining % 86400) // 3600
            e = premium_embed(
                f"✨ This server has **Premium**!\nExpires in {days}d {hours}h."
            )
            e.set_author(name="Premium Status")
        else:
            e = embed(
                title="✨ Premium",
                description="This server does not have Premium.\n\n**Premium Features:**\n• Unlimited giveaways\n• Custom bot prefix\n• Advanced moderation logs\n• Priority support\n• Custom welcome messages\n• And more!",
                color=config.PREMIUM_COLOR,
            )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="genkey", description="Generate a premium key (Owner only)")
    @commands.is_owner()
    async def genkey(self, ctx, duration_days: int, amount: int = 1):
        if amount < 1 or amount > 50:
            await ctx.send(embed=error_embed("❌ Amount must be between 1-50."))
            return
        if duration_days < 1 or duration_days > 3650:
            await ctx.send(embed=error_embed("❌ Duration must be between 1-3650 days."))
            return

        keys = []
        for _ in range(amount):
            key = f"PRM-{secrets.token_hex(8).upper()}"
            await db.execute(
                "INSERT INTO premium_keys (key, duration_days, created_at) VALUES (?, ?, ?)",
                [key, duration_days, time.time()],
            )
            keys.append(key)

        e = success_embed(f"✅ Generated **{amount}** key(s) for **{duration_days} days**")
        e.add_field(
            name="Keys",
            value="\n".join(f"`{k}`" for k in keys),
            inline=False,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="redeem", description="Redeem a premium key for this server")
    @commands.has_permissions(administrator=True)
    async def redeem(self, ctx, key: str):
        key = key.upper().strip()
        row = await db.fetchone("SELECT * FROM premium_keys WHERE key = ?", [key])
        if not row:
            await ctx.send(embed=error_embed("❌ Invalid key."))
            return
        if row["used_by"] != 0:
            await ctx.send(embed=error_embed("❌ This key has already been used."))
            return

        await db.execute("UPDATE premium_keys SET used_by = ? WHERE key = ?", [ctx.guild.id, key])

        config_row = await db.fetchone(
            "SELECT premium_until FROM guild_config WHERE guild_id = ?", [ctx.guild.id],
        )
        if config_row and config_row["premium_until"] > time.time():
            new_until = config_row["premium_until"] + (row["duration_days"] * 86400)
        else:
            new_until = time.time() + (row["duration_days"] * 86400)

        await db.execute(
            "INSERT OR REPLACE INTO guild_config (guild_id, premium_until) VALUES (?, ?)",
            [ctx.guild.id, new_until],
        )

        expiry = f"<t:{int(new_until)}:F>"
        e = premium_embed(
            f"✅ **Premium activated!**\nDuration: {row['duration_days']} days\nExpires: {expiry}"
        )
        await ctx.send(embed=e)

        try:
            await ctx.guild.system_channel.send(
                embed=premium_embed(f"✨ This server now has **Premium**! Thank you for your support!")
            )
        except:
            pass

    @commands.hybrid_command(name="keys", description="List all premium keys (Owner only)")
    @commands.is_owner()
    async def keys(self, ctx):
        rows = await db.fetchall(
            "SELECT * FROM premium_keys ORDER BY created_at DESC LIMIT 20",
        )
        if not rows:
            await ctx.send(embed=error_embed("❌ No keys found."))
            return

        desc = []
        for row in rows:
            status = f"Used by guild {row['used_by']}" if row["used_by"] else "Available"
            desc.append(f"`{row['key']}` — {row['duration_days']}d — {status}")

        e = embed(title="🔑 Premium Keys", description="\n".join(desc))
        await ctx.send(embed=e)

    @commands.hybrid_command(name="premium_features", description="Show all premium features")
    async def premium_features(self, ctx):
        e = premium_embed(
            "✨ **Premium Features:**\n\n"
            "• **Unlimited Giveaways** — No limits on giveaways\n"
            "• **Custom Prefix** — Set your own bot prefix\n"
            "• **Advanced Mod Logs** — Detailed moderation logging\n"
            "• **Custom Welcome** — Personalized welcome messages\n"
            "• **Priority Support** — Direct support channel\n"
            "• **More Commands** — Exclusive premium commands\n"
            "• **Higher Limits** — Increased command cooldowns\n\n"
            "Use `/redeem <key>` to activate Premium on this server."
        )
        e.set_author(name="✨ Premium", icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=e)


async def setup(bot):
    await bot.add_cog(Premium(bot))
