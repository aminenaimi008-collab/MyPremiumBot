import discord
import config
import time
from bot.database import db


async def is_premium(guild_id: int) -> bool:
    row = await db.fetchone(
        "SELECT premium_until FROM guild_config WHERE guild_id = ?", [guild_id],
    )
    if not row or row["premium_until"] == 0:
        return False
    return time.time() < row["premium_until"]


async def require_premium(ctx) -> bool:
    if await is_premium(ctx.guild.id):
        return True
    await ctx.send(embed=premium_embed(
        "✨ This feature requires **Premium**!\n\n"
        "Get Premium from the server owner to unlock:\n"
        "• Unlimited giveaways\n"
        "• Custom prefix\n"
        "• Advanced logs\n"
        "• And more!"
    ))
    return False


def embed(
    title="",
    description="",
    color=config.EMBED_COLOR,
    fields=None,
    footer=None,
    author=None,
    thumbnail=None,
    image=None,
    timestamp=None,
):
    e = discord.Embed(title=title, description=description, color=color, timestamp=timestamp)
    if fields:
        for field in fields:
            if len(field) == 3:
                name, value, inline = field
            else:
                name, value = field
                inline = False
            e.add_field(name=name, value=value, inline=inline)
    if footer:
        e.set_footer(text=footer)
    if author:
        e.set_author(**author)
    if thumbnail:
        e.set_thumbnail(url=thumbnail)
    if image:
        e.set_image(url=image)
    return e


def error_embed(description):
    return embed(description=description, color=config.ERROR_COLOR)


def success_embed(description):
    return embed(description=description, color=config.SUCCESS_COLOR)


def premium_embed(description):
    return embed(description=description, color=config.PREMIUM_COLOR)


def has_permissions(member, **perms):
    return all(getattr(member.guild_permissions, perm, False) for perm in perms)


def format_time(timestamp):
    return f"<t:{int(timestamp)}:R>"


def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"
