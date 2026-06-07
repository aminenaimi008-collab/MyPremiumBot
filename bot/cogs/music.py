import discord
from discord.ext import commands
import yt_dlp
import asyncio
import re
import config
from bot.utils.helpers import embed, error_embed, success_embed

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}


class Song:
    def __init__(self, url, title, duration, requester, thumbnail=None):
        self.url = url
        self.title = title
        self.duration = duration
        self.requester = requester
        self.thumbnail = thumbnail

    def __str__(self):
        return f"[{self.title}]({self.url})"

    def format_duration(self):
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"


class Player:
    def __init__(self, bot, guild_id):
        self.bot = bot
        self.guild_id = guild_id
        self.queue = []
        self.current = None
        self.loop = False
        self.loop_queue = False
        self.vc = None
        self.volume = 0.5

    async def connect(self, channel):
        if self.vc and self.vc.is_connected():
            await self.vc.move_to(channel)
        else:
            self.vc = await channel.connect()

    async def disconnect(self):
        self.queue.clear()
        self.current = None
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()
        self.vc = None

    async def play_next(self, error=None):
        if error:
            print(f"Player error: {error}")

        if self.loop and self.current:
            self.queue.insert(0, self.current)

        if self.loop_queue and self.current:
            self.queue.append(self.current)

        if self.queue:
            self.current = self.queue.pop(0)
            await self._play_current()
        else:
            self.current = None

    async def _play_current(self):
        if not self.vc or not self.vc.is_connected():
            return

        try:
            source = await discord.FFmpegOpusAudio.from_probe(
                self.current.url,
                **FFMPEG_OPTIONS,
            )
            source.volume = self.volume
            self.vc.play(source, after=self.play_next)
        except Exception as e:
            print(f"Play error: {e}")
            await self.play_next()

    def is_playing(self):
        return self.vc and self.vc.is_playing()

    def is_paused(self):
        return self.vc and self.vc.is_paused()


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    def get_player(self, guild_id):
        if guild_id not in self.players:
            self.players[guild_id] = Player(self.bot, guild_id)
        return self.players[guild_id]

    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send(embed=error_embed("❌ You must be in a voice channel."))
            return False
        player = self.get_player(ctx.guild.id)
        if player.vc and player.vc.is_connected():
            if ctx.author.voice.channel != player.vc.channel:
                await ctx.send(embed=error_embed("❌ You must be in the same voice channel."))
                return False
        return True

    @commands.hybrid_command(name="play", description="Play a song from YouTube")
    async def play(self, ctx, *, query):
        if not await self.ensure_voice(ctx):
            return

        player = self.get_player(ctx.guild.id)
        if not player.vc or not player.vc.is_connected():
            if ctx.author.voice:
                await player.connect(ctx.author.voice.channel)

        await ctx.defer()

        try:
            async with ctx.typing():
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: self._search_youtube(query))

                if not data:
                    await ctx.send(embed=error_embed("❌ No results found."))
                    return

                song = Song(
                    url=data["url"],
                    title=data["title"],
                    duration=data["duration"],
                    requester=ctx.author,
                    thumbnail=data.get("thumbnail"),
                )

                player.queue.append(song)

                if not player.is_playing():
                    await player.play_next()
                    e = success_embed(f"🎵 Now playing: **{song.title}** ({song.format_duration()})")
                else:
                    e = embed(
                        title="🎵 Added to Queue",
                        description=f"**{song.title}** ({song.format_duration()})",
                        color=config.EMBED_COLOR,
                        fields=[("Position", str(len(player.queue)), True), ("Requested by", ctx.author.mention, True)],
                    )

                await ctx.send(embed=e)

        except Exception as e:
            await ctx.send(embed=error_embed(f"❌ Error: {str(e)[:100]}"))

    def _search_youtube(self, query):
        url_pattern = re.match(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+", query)
        if url_pattern:
            ydl_url = query
        else:
            ydl_url = f"ytsearch1:{query}"

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(ydl_url, download=False)

            if "entries" in info:
                info = info["entries"][0]

            return {
                "url": info["url"],
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail"),
            }

    @commands.hybrid_command(name="skip", description="Skip the current song")
    async def skip(self, ctx):
        if not await self.ensure_voice(ctx):
            return
        player = self.get_player(ctx.guild.id)
        if player.is_playing():
            player.vc.stop()
            await ctx.send(embed=success_embed("⏭️ Skipped."))
        else:
            await ctx.send(embed=error_embed("❌ Nothing is playing."))

    @commands.hybrid_command(name="stop", description="Stop playback and clear queue")
    async def stop(self, ctx):
        if not await self.ensure_voice(ctx):
            return
        player = self.get_player(ctx.guild.id)
        if player.vc and player.vc.is_connected():
            player.queue.clear()
            player.vc.stop()
            await player.disconnect()
            await ctx.send(embed=success_embed("⏹️ Stopped and disconnected."))

    @commands.hybrid_command(name="pause", description="Pause the current song")
    async def pause(self, ctx):
        if not await self.ensure_voice(ctx):
            return
        player = self.get_player(ctx.guild.id)
        if player.is_playing():
            player.vc.pause()
            await ctx.send(embed=success_embed("⏸️ Paused."))
        else:
            await ctx.send(embed=error_embed("❌ Nothing is playing."))

    @commands.hybrid_command(name="resume", description="Resume the current song")
    async def resume(self, ctx):
        if not await self.ensure_voice(ctx):
            return
        player = self.get_player(ctx.guild.id)
        if player.is_paused():
            player.vc.resume()
            await ctx.send(embed=success_embed("▶️ Resumed."))
        else:
            await ctx.send(embed=error_embed("❌ Nothing is paused."))

    @commands.hybrid_command(name="queue", description="View the music queue")
    async def queue(self, ctx):
        player = self.get_player(ctx.guild.id)
        if not player.current and not player.queue:
            await ctx.send(embed=error_embed("❌ Queue is empty."))
            return

        desc = []
        if player.current:
            desc.append(f"**Now Playing:** {player.current.title} ({player.current.format_duration()})")

        if player.queue:
            desc.append(f"\n**Up Next ({len(player.queue)} songs):**")
            for i, song in enumerate(player.queue[:10], 1):
                desc.append(f"{i}. {song.title} ({song.format_duration()})")
            if len(player.queue) > 10:
                desc.append(f"... and {len(player.queue) - 10} more")

        e = embed(title="🎶 Music Queue", description="\n".join(desc))
        await ctx.send(embed=e)

    @commands.hybrid_command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, ctx):
        player = self.get_player(ctx.guild.id)
        if not player.current:
            await ctx.send(embed=error_embed("❌ Nothing is playing."))
            return

        e = embed(
            title="🎶 Now Playing",
            description=f"**{player.current.title}** ({player.current.format_duration()})",
            fields=[("Requested by", player.current.requester.mention, False)],
            thumbnail=player.current.thumbnail,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="volume", description="Set the volume (0-100)")
    async def volume(self, ctx, vol: int):
        if not await self.ensure_voice(ctx):
            return
        if vol < 0 or vol > 100:
            await ctx.send(embed=error_embed("❌ Volume must be between 0-100."))
            return
        player = self.get_player(ctx.guild.id)
        player.volume = vol / 100
        if player.vc and player.vc.source:
            player.vc.source.volume = player.volume
        await ctx.send(embed=success_embed(f"🔊 Volume set to {vol}%"))

    @commands.hybrid_command(name="loop", description="Toggle loop for current song")
    async def loop(self, ctx):
        if not await self.ensure_voice(ctx):
            return
        player = self.get_player(ctx.guild.id)
        player.loop = not player.loop
        if player.loop_queue:
            player.loop_queue = False
        status = "enabled" if player.loop else "disabled"
        await ctx.send(embed=success_embed(f"🔁 Loop {status}."))

    @commands.hybrid_command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, ctx):
        if not await self.ensure_voice(ctx):
            return
        import random
        player = self.get_player(ctx.guild.id)
        if len(player.queue) < 2:
            await ctx.send(embed=error_embed("❌ Not enough songs in queue."))
            return
        random.shuffle(player.queue)
        await ctx.send(embed=success_embed("🔀 Queue shuffled."))

    @commands.hybrid_command(name="join", description="Join your voice channel")
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send(embed=error_embed("❌ You must be in a voice channel."))
            return
        player = self.get_player(ctx.guild.id)
        await player.connect(ctx.author.voice.channel)
        await ctx.send(embed=success_embed(f"✅ Joined {ctx.author.voice.channel.mention}"))

    @commands.hybrid_command(name="leave", description="Leave the voice channel")
    async def leave(self, ctx):
        if not await self.ensure_voice(ctx):
            return
        player = self.get_player(ctx.guild.id)
        await player.disconnect()
        await ctx.send(embed=success_embed("👋 Disconnected."))


async def setup(bot):
    await bot.add_cog(Music(bot))
