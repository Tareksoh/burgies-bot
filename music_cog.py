from __future__ import annotations

import asyncio
import random
import os
import base64
import discord
from discord.ext import commands
from collections import deque
import yt_dlp


def _get_cookies_file() -> str | None:
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    if os.path.exists(local):
        print(f'[Cookies] Using local file: {local}')
        return local
    print('[Cookies] No cookies.txt found')
    return None

# yt-dlp options — no download, stream directly
YDL_OPTS = {
    'format': 'best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'noplaylist': True,
    'extract_flat': False,
    'source_address': '0.0.0.0',
    'extractor_args': {
        'youtube': {
            'player_client': ['web_embedded', 'mweb', 'android_vr'],
        }
    },
}


def build_ffmpeg_opts(http_headers: dict) -> dict:
    # Forward yt-dlp's HTTP headers to FFmpeg so YouTube doesn't reject the stream
    header_str = ''.join(f'{k}: {v}\r\n' for k, v in http_headers.items())
    before = f'-headers "{header_str}" ' if header_str else ''
    before += '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    return {'before_options': before, 'options': '-vn'}


class Song:
    def __init__(self, source_url, title, duration, webpage_url, thumbnail=None, requester=None, http_headers=None):
        self.source_url = source_url
        self.title = title
        self.duration = duration
        self.webpage_url = webpage_url
        self.thumbnail = thumbnail
        self.requester = requester
        self.http_headers: dict = http_headers or {}

    def format_duration(self):
        if not self.duration:
            return 'Live / Unknown'
        mins, secs = divmod(int(self.duration), 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f'{hours}:{mins:02d}:{secs:02d}'
        return f'{mins}:{secs:02d}'


class MusicPlayer:
    def __init__(self, guild_id, bot):
        self.guild_id = guild_id
        self.bot = bot
        self.queue: deque[Song] = deque()
        self.current: Song | None = None
        self.loop = False
        self.volume = 0.5
        self._ctx = None

    def set_ctx(self, ctx):
        self._ctx = ctx

    def _after_song(self, error):
        if error:
            print(f'[Player Error] {error}')
            import traceback
            traceback.print_exception(type(error), error, error.__traceback__)

        if self.loop and self.current:
            self.queue.appendleft(self.current)

        if self.queue:
            next_song = self.queue.popleft()
            self.current = next_song
            coro = self._play(next_song)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
        else:
            self.current = None

    async def _play(self, song: Song):
        vc = self._ctx.voice_client
        if not vc or not vc.is_connected():
            return

        source = discord.FFmpegPCMAudio(song.source_url, **build_ffmpeg_opts(song.http_headers))
        source = discord.PCMVolumeTransformer(source, volume=self.volume)
        vc.play(source, after=self._after_song)

        embed = now_playing_embed(song)
        await self._ctx.send(embed=embed)

    async def start(self, ctx, song: Song):
        self.set_ctx(ctx)
        self.current = song
        await self._play(song)

    async def add(self, song: Song):
        self.queue.append(song)


def now_playing_embed(song: Song) -> discord.Embed:
    embed = discord.Embed(
        title='Now Playing',
        description=f'[{song.title}]({song.webpage_url})',
        color=0x1DB954,
    )
    embed.add_field(name='Duration', value=song.format_duration())
    if song.requester:
        embed.add_field(name='Requested by', value=song.requester.mention)
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    return embed


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}

        # Optional Spotify support
        self._setup_spotify()

    def _setup_spotify(self):
        self.sp = None
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if client_id and client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials
                auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
                self.sp = spotipy.Spotify(auth_manager=auth)
                print('Spotify integration enabled.')
            except ImportError:
                print('spotipy not installed — Spotify support disabled.')
        else:
            print('Spotify credentials not set — Spotify support disabled.')

    def get_player(self, ctx) -> MusicPlayer:
        gid = ctx.guild.id
        if gid not in self.players:
            self.players[gid] = MusicPlayer(gid, self.bot)
        self.players[gid].set_ctx(ctx)
        return self.players[gid]

    async def _ensure_voice(self, ctx) -> bool:
        """Join voice channel if not connected. Returns True if connected."""
        if ctx.voice_client and ctx.voice_client.is_connected():
            return True
        if not ctx.author.voice:
            await ctx.send('You need to be in a voice channel first!')
            return False
        await ctx.author.voice.channel.connect()
        return True

    # ── resolvers ──────────────────────────────────────────────────────────────

    async def _resolve(self, query: str, requester) -> 'Song | list[Song] | None':
        """Detect platform and resolve to Song(s)."""
        if 'spotify.com' in query:
            return await self._resolve_spotify(query, requester)
        return await self._resolve_ydl(query, requester)

    async def _resolve_ydl(self, url: str, requester) -> 'Song | None':
        loop = asyncio.get_event_loop()

        def extract():
            opts = dict(YDL_OPTS)
            cookies = _get_cookies_file()
            if cookies:
                opts['cookiefile'] = cookies
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                return info

        info = await loop.run_in_executor(None, extract)
        if not info:
            return None

        return Song(
            source_url=info['url'],
            title=info.get('title', 'Unknown'),
            duration=info.get('duration'),
            webpage_url=info.get('webpage_url', url),
            thumbnail=info.get('thumbnail'),
            requester=requester,
            http_headers=info.get('http_headers', {}),
        )

    async def _resolve_spotify(self, url: str, requester) -> 'Song | list[Song] | None':
        if not self.sp:
            raise Exception(
                'Spotify is not configured. Add `SPOTIFY_CLIENT_ID` and '
                '`SPOTIFY_CLIENT_SECRET` to your `.env` file.'
            )

        loop = asyncio.get_event_loop()

        if '/track/' in url:
            track = await loop.run_in_executor(None, lambda: self.sp.track(url))
            query = f"{track['name']} {track['artists'][0]['name']} official audio"
            return await self._resolve_ydl(f'ytsearch:{query}', requester)

        elif '/playlist/' in url:
            results = await loop.run_in_executor(None, lambda: self.sp.playlist_tracks(url))
            songs = []
            for item in results['items'][:30]:
                track = item.get('track')
                if not track:
                    continue
                query = f"{track['name']} {track['artists'][0]['name']}"
                try:
                    song = await self._resolve_ydl(f'ytsearch:{query}', requester)
                    if song:
                        songs.append(song)
                except Exception:
                    continue
            return songs

        elif '/album/' in url:
            album = await loop.run_in_executor(None, lambda: self.sp.album_tracks(url))
            songs = []
            for track in album['items'][:30]:
                query = f"{track['name']} {track['artists'][0]['name']}"
                try:
                    song = await self._resolve_ydl(f'ytsearch:{query}', requester)
                    if song:
                        songs.append(song)
                except Exception:
                    continue
            return songs

        raise Exception('Unsupported Spotify URL. Use a track, playlist, or album link.')

    # ── commands ───────────────────────────────────────────────────────────────

    @commands.command(name='join', aliases=['j', 'connect'])
    async def join(self, ctx):
        """Join your voice channel."""
        if not ctx.author.voice:
            return await ctx.send('You need to be in a voice channel first!')
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f'Joined **{channel.name}**')

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, query: str):
        """Play from a YouTube/Spotify/SoundCloud URL or search YouTube."""
        if not await self._ensure_voice(ctx):
            return

        async with ctx.typing():
            try:
                is_url = query.startswith(('http://', 'https://'))
                search_query = query if is_url else f'ytsearch:{query}'

                result = await self._resolve(search_query, ctx.author)

                if result is None:
                    return await ctx.send('Could not find anything for that query.')

                player = self.get_player(ctx)
                vc = ctx.voice_client

                if isinstance(result, list):
                    for song in result:
                        await player.add(song)
                    embed = discord.Embed(
                        title='Playlist Added',
                        description=f'Added **{len(result)}** songs to the queue.',
                        color=0x1DB954,
                    )
                    await ctx.send(embed=embed)
                    if not vc.is_playing() and not vc.is_paused():
                        next_song = player.queue.popleft()
                        await player.start(ctx, next_song)
                    return

                if vc.is_playing() or vc.is_paused():
                    await player.add(result)
                    embed = discord.Embed(
                        title='Added to Queue',
                        description=f'[{result.title}]({result.webpage_url})',
                        color=0x0099FF,
                    )
                    embed.add_field(name='Duration', value=result.format_duration())
                    embed.add_field(name='Position', value=f'#{len(player.queue)}')
                    if result.requester:
                        embed.add_field(name='Requested by', value=result.requester.mention)
                    await ctx.send(embed=embed)
                else:
                    await player.start(ctx, result)

            except Exception as e:
                import traceback
                traceback.print_exc()
                await ctx.send(f'Error: {e}')

    @commands.command(name='pause')
    async def pause(self, ctx):
        """Pause playback."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send('Paused.')
        else:
            await ctx.send('Nothing is playing.')

    @commands.command(name='resume', aliases=['r'])
    async def resume(self, ctx):
        """Resume paused playback."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send('Resumed.')
        else:
            await ctx.send('Not paused.')

    @commands.command(name='skip', aliases=['s', 'next'])
    async def skip(self, ctx):
        """Skip the current song."""
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send('Skipped.')
        else:
            await ctx.send('Nothing is playing.')

    @commands.command(name='stop')
    async def stop(self, ctx):
        """Stop playback and clear the queue."""
        player = self.get_player(ctx)
        player.queue.clear()
        player.current = None
        player.loop = False
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send('Stopped and queue cleared.')

    @commands.command(name='loop', aliases=['l'])
    async def loop_cmd(self, ctx):
        """Toggle looping the current song."""
        player = self.get_player(ctx)
        player.loop = not player.loop
        state = 'on' if player.loop else 'off'
        await ctx.send(f'Loop is now **{state}**.')

    @commands.command(name='volume', aliases=['vol', 'v'])
    async def volume(self, ctx, vol: int):
        """Set volume (0–100)."""
        if not ctx.voice_client:
            return await ctx.send('Not in a voice channel.')
        if not 0 <= vol <= 100:
            return await ctx.send('Volume must be between 0 and 100.')
        player = self.get_player(ctx)
        player.volume = vol / 100
        if ctx.voice_client.source:
            ctx.voice_client.source.volume = vol / 100
        await ctx.send(f'Volume set to **{vol}%**.')

    @commands.command(name='queue', aliases=['q'])
    async def queue_cmd(self, ctx):
        """Show the current queue."""
        player = self.get_player(ctx)

        if not player.current and not player.queue:
            return await ctx.send('The queue is empty.')

        embed = discord.Embed(title='Music Queue', color=0x0099FF)

        if player.current:
            embed.add_field(
                name='Now Playing',
                value=f'[{player.current.title}]({player.current.webpage_url}) `{player.current.format_duration()}`',
                inline=False,
            )

        if player.queue:
            lines = []
            for i, song in enumerate(list(player.queue)[:10], 1):
                lines.append(f'`{i}.` [{song.title}]({song.webpage_url}) `{song.format_duration()}`')
            if len(player.queue) > 10:
                lines.append(f'*... and {len(player.queue) - 10} more*')
            embed.add_field(name='Up Next', value='\n'.join(lines), inline=False)

        embed.set_footer(text=f'Loop: {"On" if player.loop else "Off"} | Songs in queue: {len(player.queue)}')
        await ctx.send(embed=embed)

    @commands.command(name='nowplaying', aliases=['np', 'current'])
    async def nowplaying(self, ctx):
        """Show the currently playing song."""
        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('Nothing is playing right now.')
        await ctx.send(embed=now_playing_embed(player.current))

    @commands.command(name='shuffle')
    async def shuffle(self, ctx):
        """Shuffle the queue."""
        player = self.get_player(ctx)
        if len(player.queue) < 2:
            return await ctx.send('Need at least 2 songs in the queue to shuffle.')
        lst = list(player.queue)
        random.shuffle(lst)
        player.queue = deque(lst)
        await ctx.send('Queue shuffled!')

    @commands.command(name='remove', aliases=['rm'])
    async def remove(self, ctx, index: int):
        """Remove a song from the queue by its position number."""
        player = self.get_player(ctx)
        if index < 1 or index > len(player.queue):
            return await ctx.send(f'Invalid index. Queue has {len(player.queue)} song(s).')
        lst = list(player.queue)
        removed = lst.pop(index - 1)
        player.queue = deque(lst)
        await ctx.send(f'Removed **{removed.title}** from the queue.')

    @commands.command(name='clear')
    async def clear(self, ctx):
        """Clear all songs from the queue (keeps current song playing)."""
        player = self.get_player(ctx)
        player.queue.clear()
        await ctx.send('Queue cleared.')

    @commands.command(name='search', aliases=['find'])
    async def search(self, ctx, *, query: str):
        """Search YouTube and show the top 5 results."""
        async with ctx.typing():
            loop = asyncio.get_event_loop()

            def extract():
                opts = {**YDL_OPTS, 'noplaylist': True}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(f'ytsearch5:{query}', download=False)

            try:
                results = await loop.run_in_executor(None, extract)
                entries = results.get('entries', [])
                if not entries:
                    return await ctx.send('No results found.')

                lines = []
                for i, entry in enumerate(entries[:5], 1):
                    title = entry.get('title', 'Unknown')
                    url = entry.get('webpage_url', '')
                    duration = entry.get('duration', 0)
                    mins, secs = divmod(int(duration or 0), 60)
                    lines.append(f'`{i}.` [{title}]({url}) `{mins}:{secs:02d}`')

                embed = discord.Embed(
                    title=f'Search results for: {query}',
                    description='\n'.join(lines),
                    color=0xFF0000,
                )
                embed.set_footer(text=f'Use {ctx.prefix}play <URL> to play one of these')
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f'Search failed: {e}')

    @commands.command(name='leave', aliases=['disconnect', 'dc'])
    async def leave(self, ctx):
        """Disconnect from the voice channel."""
        if not ctx.voice_client:
            return await ctx.send('Not connected to a voice channel.')
        gid = ctx.guild.id
        if gid in self.players:
            self.players[gid].queue.clear()
            self.players[gid].current = None
            del self.players[gid]
        await ctx.voice_client.disconnect()
        await ctx.send('Disconnected.')


def setup(bot: commands.Bot):
    bot.add_cog(Music(bot))
