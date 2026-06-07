import discord
from discord.ext import commands
from discord.ui import Button, View
import time
import config
from bot.database import db
from bot.utils.helpers import embed, error_embed, success_embed

TICKET_EMOJIS = {
    "support": "❓",
    "report": "🚨",
    "billing": "💰",
    "apply": "📝",
    "other": "📋",
}


class TicketView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Create Ticket", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        existing = await db.fetchone(
            "SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'",
            [interaction.guild.id, interaction.user.id],
        )
        if existing:
            channel = interaction.guild.get_channel(existing["channel_id"])
            if channel:
                await interaction.response.send_message(
                    embed=error_embed(f"❌ You already have an open ticket: {channel.mention}"),
                    ephemeral=True,
                )
                return
            await db.execute(
                "UPDATE tickets SET status = 'closed' WHERE id = ?", [existing["id"]],
            )

        config_row = await db.fetchone(
            "SELECT ticket_category FROM guild_config WHERE guild_id = ?", [interaction.guild.id],
        )
        category = None
        if config_row and config_row["ticket_category"]:
            category = interaction.guild.get_channel(config_row["ticket_category"])

        if not category:
            category = discord.utils.get(interaction.guild.categories, name=config.TICKET_CATEGORY_NAME)
            if not category:
                overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    interaction.guild.me: discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, manage_channels=True,
                    ),
                }
                category = await interaction.guild.create_category(config.TICKET_CATEGORY_NAME, overwrites=overwrites)

        ticket_channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name.lower().replace(' ', '-')[:20]}",
            category=category,
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            },
            topic=f"User ID: {interaction.user.id}",
        )

        await db.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, status, created_at) VALUES (?, ?, ?, 'open', ?)",
            [interaction.guild.id, ticket_channel.id, interaction.user.id, time.time()],
        )

        close_view = CloseTicketView()
        e = embed(
            title="🎫 New Ticket",
            description=f"Welcome {interaction.user.mention}!\nDescribe your issue and staff will be with you shortly.\n\n**Ticket Types:**\n• ❓ Support - General help\n• 🚨 Report - Report a user\n• 💰 Billing - Payment issues\n• 📝 Apply - Staff applications",
            color=config.SUCCESS_COLOR,
            footer="Click the button below to close this ticket",
        )
        await ticket_channel.send(content=interaction.user.mention, embed=e, view=close_view)

        await interaction.response.send_message(
            embed=success_embed(f"✅ Ticket created: {ticket_channel.mention}"),
            ephemeral=True,
        )


class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        ticket = await db.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
            [interaction.channel.id],
        )
        if not ticket:
            await interaction.response.send_message(embed=error_embed("❌ This is not an open ticket."), ephemeral=True)
            return

        confirm_view = ConfirmCloseView(ticket)
        await interaction.response.send_message(
            embed=embed(description="Are you sure you want to close this ticket?", color=config.ERROR_COLOR),
            view=confirm_view,
            ephemeral=True,
        )


class ConfirmCloseView(View):
    def __init__(self, ticket):
        super().__init__(timeout=60)
        self.ticket = ticket

    @discord.ui.button(label="Yes, Close", emoji="🔒", style=discord.ButtonStyle.danger)
    async def confirm_close(self, interaction: discord.Interaction, button: Button):
        await db.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", [self.ticket["id"]])
        await interaction.channel.send(embed=embed(
            title="🔒 Ticket Closed",
            description=f"Closed by {interaction.user.mention}\nThis channel will be deleted in 10 seconds.",
            color=config.ERROR_COLOR,
        ))
        await interaction.response.send_message(embed=success_embed("✅ Ticket closed."), ephemeral=True)
        await interaction.channel.edit(sync_permissions=True)
        await interaction.channel.send("⏳ Deleting in 10s...")
        import asyncio
        await asyncio.sleep(10)
        await interaction.channel.delete()

    @discord.ui.button(label="Cancel", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def cancel_close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ Cancelled.", view=None, embed=None)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketView(bot))
        self.bot.add_view(CloseTicketView())

    @commands.hybrid_command(name="ticket", description="Send the ticket creation panel")
    @commands.has_permissions(administrator=True)
    async def ticket_panel(self, ctx):
        e = embed(
            title="🎫 Support Tickets",
            description="Click the button below to create a ticket.\nOur staff will assist you as soon as possible.",
            fields=[
                ("How it works", "1. Click **Create Ticket**\n2. A private channel will be created\n3. Describe your issue\n4. Staff will help you"),
                ("Rules", "• Do not create unnecessary tickets\n• Be respectful to staff\n• Close the ticket when resolved"),
            ],
            color=config.EMBED_COLOR,
            footer="Support Team",
        )
        await ctx.send(embed=e, view=TicketView(self.bot))

    @commands.hybrid_command(name="adduser", description="Add a user to the ticket")
    @commands.has_permissions(manage_channels=True)
    async def adduser(self, ctx, member: discord.Member):
        ticket = await db.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'", [ctx.channel.id],
        )
        if not ticket:
            await ctx.send(embed=error_embed("❌ This is not an open ticket channel."))
            return
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
        await ctx.send(embed=success_embed(f"✅ Added {member.mention} to the ticket."))

    @commands.hybrid_command(name="removeuser", description="Remove a user from the ticket")
    @commands.has_permissions(manage_channels=True)
    async def removeuser(self, ctx, member: discord.Member):
        ticket = await db.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'", [ctx.channel.id],
        )
        if not ticket:
            await ctx.send(embed=error_embed("❌ This is not an open ticket channel."))
            return
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(embed=success_embed(f"✅ Removed {member.mention} from the ticket."))

    @commands.hybrid_command(name="rename", description="Rename the ticket channel")
    @commands.has_permissions(manage_channels=True)
    async def rename(self, ctx, *, name):
        ticket = await db.fetchone(
            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'", [ctx.channel.id],
        )
        if not ticket:
            await ctx.send(embed=error_embed("❌ This is not an open ticket channel."))
            return
        await ctx.channel.edit(name=name[:30])
        await ctx.send(embed=success_embed(f"✅ Channel renamed to #{name[:30]}"))


async def setup(bot):
    await bot.add_cog(Tickets(bot))
