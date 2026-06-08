import discord
from discord.ext import commands
from discord.ui import Button, View
import time
import random
import asyncio
import config
from bot.database import db
from bot.utils.helpers import embed, error_embed, success_embed, is_premium


class GiveawayView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Enter", emoji="🎉", style=discord.ButtonStyle.success, custom_id="enter_giveaway")
    async def enter(self, interaction: discord.Interaction, button: Button):
        giveaway = await db.fetchone(
            "SELECT * FROM giveaways WHERE message_id = ? AND ended = 0",
            [interaction.message.id],
        )
        if not giveaway:
            await interaction.response.send_message(embed=error_embed("❌ Giveaway not found or ended."), ephemeral=True)
            return

        participant = await db.fetchone(
            "SELECT * FROM giveaway_participants WHERE giveaway_id = ? AND user_id = ?",
            [giveaway["id"], interaction.user.id],
        )
        if participant:
            await db.execute(
                "DELETE FROM giveaway_participants WHERE giveaway_id = ? AND user_id = ?",
                [giveaway["id"], interaction.user.id],
            )
            await interaction.response.send_message(embed=embed(description="❌ You left the giveaway."), ephemeral=True)
        else:
            await db.execute(
                "INSERT OR IGNORE INTO giveaway_participants (giveaway_id, user_id) VALUES (?, ?)",
                [giveaway["id"], interaction.user.id],
            )
            await interaction.response.send_message(embed=embed(description="✅ You entered the giveaway!"), ephemeral=True)

    async def update_message(self, message, giveaway):
        remaining = giveaway["ends_at"] - time.time()
        if remaining <= 0:
            await self.end_giveaway(message, giveaway)
            return

        participant_ids = await db.fetchall(
            "SELECT user_id FROM giveaway_participants WHERE giveaway_id = ?", [giveaway["id"]],
        )
        count = len(participant_ids)

        e = embed(
            title="🎉 Giveaway",
            description=f"**Prize:** {giveaway['prize']}\n**Winners:** {giveaway['winners']}\n**Ends:** <t:{int(giveaway['ends_at'])}:R>",
            fields=[("Participants", str(count), True), ("Host", f"<@{giveaway['host_id']}>", True)],
            color=config.SUCCESS_COLOR,
        )
        await message.edit(embed=e, view=self)

    async def end_giveaway(self, message, giveaway):
        participant_ids = await db.fetchall(
            "SELECT user_id FROM giveaway_participants WHERE giveaway_id = ?", [giveaway["id"]],
        )
        await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", [giveaway["id"]])

        if not participant_ids:
            e = embed(
                title="🎉 Giveaway Ended",
                description=f"**Prize:** {giveaway['prize']}\nNo participants.",
                color=config.ERROR_COLOR,
            )
            await message.edit(embed=e, view=None)
            return

        winners_count = min(giveaway["winners"], len(participant_ids))
        winners = random.sample([p["user_id"] for p in participant_ids], winners_count)
        winner_mentions = [f"<@{w}>" for w in winners]

        e = embed(
            title="🎉 Giveaway Ended",
            description=f"**Prize:** {giveaway['prize']}\n**Winner(s):** {', '.join(winner_mentions)}",
            color=config.SUCCESS_COLOR,
        )
        await message.edit(embed=e, view=None)
        await message.reply(f"🎉 Congratulations {' '.join(winner_mentions)}! You won **{giveaway['prize']}**!")


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        giveaways = await db.fetchall("SELECT * FROM giveaways WHERE ended = 0")
        for g in giveaways:
            channel = self.bot.get_channel(g["channel_id"])
            if not channel:
                continue
            try:
                msg = await channel.fetch_message(g["message_id"])
                view = GiveawayView()
                remaining = g["ends_at"] - time.time()
                if remaining <= 0:
                    await view.end_giveaway(msg, g)
                else:
                    asyncio.create_task(self._wait_and_end(g, msg, view))
            except:
                await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", [g["id"]])

    async def _wait_and_end(self, giveaway, message, view):
        remaining = giveaway["ends_at"] - time.time()
        if remaining > 0:
            await asyncio.sleep(remaining)
        await view.end_giveaway(message, giveaway)

    @commands.hybrid_command(name="giveaway", description="Start a giveaway")
    @commands.has_permissions(manage_guild=True)
    async def giveaway(self, ctx, duration: str, winners: int, *, prize):
        if winners < 1 or winners > 20:
            await ctx.send(embed=error_embed("❌ Winners must be between 1-20."))
            return

        seconds = self._parse_duration(duration)
        if not seconds or seconds < 10:
            await ctx.send(embed=error_embed("❌ Invalid duration. Use format: 1h, 30m, 1d, 2d12h"))
            return

        if not await is_premium(ctx.guild.id):
            active = await db.fetchone(
                "SELECT COUNT(*) as count FROM giveaways WHERE guild_id = ? AND ended = 0",
                [ctx.guild.id],
            )
            if active["count"] >= 1:
                await ctx.send(embed=error_embed("❌ Free servers can only have **1 active giveaway**. Upgrade to Premium for unlimited!"))
                return

        ends_at = time.time() + seconds

        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_participants (
                giveaway_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (giveaway_id, user_id)
            )
        """)
        await db.db.commit()

        e = embed(
            title="🎉 Giveaway",
            description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(ends_at)}:R>",
            fields=[("Host", ctx.author.mention)],
            color=config.SUCCESS_COLOR,
        )
        msg = await ctx.send(embed=e, view=GiveawayView())

        await db.execute(
            "INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winners, ends_at, host_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [ctx.guild.id, ctx.channel.id, msg.id, prize, winners, ends_at, ctx.author.id],
        )
        await ctx.message.delete()

    @commands.hybrid_command(name="reroll", description="Reroll a giveaway winner")
    @commands.has_permissions(manage_guild=True)
    async def reroll(self, ctx, message_id: str):
        try:
            msg_id = int(message_id)
        except ValueError:
            await ctx.send(embed=error_embed("❌ Invalid message ID."))
            return

        giveaway = await db.fetchone(
            "SELECT * FROM giveaways WHERE message_id = ? AND ended = 1", [msg_id],
        )
        if not giveaway:
            await ctx.send(embed=error_embed("❌ Giveaway not found or not ended."))
            return

        participant_ids = await db.fetchall(
            "SELECT user_id FROM giveaway_participants WHERE giveaway_id = ?", [giveaway["id"]],
        )
        if not participant_ids:
            await ctx.send(embed=error_embed("❌ No participants to reroll."))
            return

        winner = random.choice(participant_ids)
        await ctx.send(f"🎉 New winner: <@{winner['user_id']}>! You won **{giveaway['prize']}**!")

    @commands.hybrid_command(name="endgiveaway", description="End a giveaway early")
    @commands.has_permissions(manage_guild=True)
    async def endgiveaway(self, ctx, message_id: str):
        try:
            msg_id = int(message_id)
        except ValueError:
            await ctx.send(embed=error_embed("❌ Invalid message ID."))
            return

        giveaway = await db.fetchone(
            "SELECT * FROM giveaways WHERE message_id = ? AND ended = 0", [msg_id],
        )
        if not giveaway:
            await ctx.send(embed=error_embed("❌ Active giveaway not found."))
            return

        await db.execute("UPDATE giveaways SET ends_at = ? WHERE id = ?", [time.time(), giveaway["id"]])
        await ctx.send(embed=success_embed("✅ Giveaway ended!"))

        channel = self.bot.get_channel(giveaway["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(msg_id)
                await GiveawayView().end_giveaway(msg, giveaway)
            except:
                pass

    def _parse_duration(self, duration):
        total = 0
        import re
        pattern = re.findall(r"(\d+)([dhms])", duration.lower())
        if not pattern:
            return None
        for value, unit in pattern:
            value = int(value)
            if unit == "d":
                total += value * 86400
            elif unit == "h":
                total += value * 3600
            elif unit == "m":
                total += value * 60
            elif unit == "s":
                total += value
        return total


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
