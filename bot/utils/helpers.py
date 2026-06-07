import discord
import config


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
        for name, value, inline in fields:
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
