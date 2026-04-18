from __future__ import annotations

import asyncio
import io
import os
import discord
from discord.ext import commands

# ── Arabic voice commands (Khaleeji dialect) ──────────────────────────────────
# Each command maps to a list of trigger keywords that Whisper might transcribe.
# Includes MSA, Khaleeji slang, and transliterated English loanwords.
COMMANDS = {
    'stop':        ['وقف', 'وقفي', 'سكر', 'سكري', 'طفي', 'طفيه', 'بس', 'خلاص', 'ستوب', 'اوقف', 'أوقف', 'كفي', 'لا'],
    'skip':        ['غير', 'غيري', 'غيرها', 'التالي', 'التالية', 'حول', 'حولي', 'سكب', 'نكست', 'بعدها', 'اللي بعدها'],
    'pause':       ['بوز', 'توقف', 'استنى', 'استني', 'لحظة', 'سكت', 'سكتي'],
    'resume':      ['كمل', 'كملي', 'رجع', 'رجعي', 'استمر', 'استمري', 'كمله', 'رجعه'],
    'play':        ['شغل', 'شغلي', 'شغله', 'شغلها', 'حط', 'حطلي', 'حطي', 'بلي'],
    'volume_up':   ['ارفع', 'ارفعي', 'ارفعه', 'عالي', 'زود', 'زودي', 'صوت اعلى', 'ارفع الصوت'],
    'volume_down': ['نزل', 'نزلي', 'نزله', 'واطي', 'خفف', 'خففي', 'نزل الصوت', 'خفض'],
}

# Ordered by priority — stop before play (since "وقف" can also mean pause)
COMMAND_PRIORITY = ['stop', 'skip', 'pause', 'resume', 'play', 'volume_up', 'volume_down']


class VoiceListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.listening: dict[int, bool] = {}
        self.model = None

    # ── Whisper model loading (lazy) ──────────────────────────────────────────

    def _load_model(self):
        if self.model is not None:
            return
        from faster_whisper import WhisperModel
        size = os.getenv('WHISPER_MODEL', 'base')
        self.model = WhisperModel(size, device='cpu', compute_type='int8')
        print(f'[Voice] Whisper model "{size}" loaded.')

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.command(name='listen', aliases=['اسمع'])
    async def listen_cmd(self, ctx):
        """Start listening for Arabic voice commands."""
        if not ctx.voice_client:
            if not ctx.author.voice:
                return await ctx.send('Join a voice channel first!')
            await ctx.author.voice.channel.connect()

        await ctx.send('Loading speech recognition model, please wait...')
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model)

        self.listening[ctx.guild.id] = True
        await ctx.send(
            '**Listening for voice commands!**\n'
            'Supported commands:\n'
            '`وقف` — stop\n'
            '`غير` — skip\n'
            '`شغل` — play / resume\n'
            '`ارفع` / `نزل` — volume up / down\n'
            '`سكت` / `لحظة` — pause\n'
            '`كمل` / `رجع` — resume\n\n'
            'Type `!stoplisten` to stop voice detection.'
        )
        asyncio.create_task(self._listen_loop(ctx))

    @commands.command(name='stoplisten', aliases=['deaf', 'اطرش'])
    async def stop_listen_cmd(self, ctx):
        """Stop listening for voice commands."""
        self.listening[ctx.guild.id] = False
        await ctx.send('Stopped listening for voice commands.')

    # ── Recording loop ────────────────────────────────────────────────────────

    async def _listen_loop(self, ctx):
        vc = ctx.voice_client
        guild_id = ctx.guild.id

        while self.listening.get(guild_id) and vc and vc.is_connected():
            try:
                sink = discord.sinks.WaveSink()
                vc.start_recording(sink, self._on_recording_done, ctx)
                await asyncio.sleep(4)

                if vc.recording:
                    vc.stop_recording()

                # Small gap so the callback can finish before next cycle
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f'[Voice] Recording loop error: {e}')
                await asyncio.sleep(2)

        self.listening[guild_id] = False
        print(f'[Voice] Stopped listening loop for guild {guild_id}.')

    async def _on_recording_done(self, sink, ctx):
        """Called each time a 4-second recording chunk finishes."""
        for user_id, audio in sink.audio_data.items():
            # Don't transcribe the bot's own audio
            if user_id == self.bot.user.id:
                continue

            audio_bytes = audio.file.getvalue()
            # Skip very short/silent clips
            if len(audio_bytes) < 3000:
                continue

            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self._transcribe, audio_bytes)

            if text:
                print(f'[Voice] Heard from {user_id}: {text}')
                await self._process_command(ctx, text)

    # ── Speech-to-text ────────────────────────────────────────────────────────

    def _transcribe(self, audio_bytes: bytes) -> str:
        try:
            segments, _ = self.model.transcribe(
                io.BytesIO(audio_bytes),
                language='ar',
                beam_size=5,
                vad_filter=True,
            )
            return ' '.join(s.text for s in segments).strip()
        except Exception as e:
            print(f'[Voice] Transcription error: {e}')
            return ''

    # ── Command matching & execution ──────────────────────────────────────────

    def _match_command(self, text: str) -> tuple[str | None, str]:
        """Return (command_name, remaining_text) or (None, '')."""
        for cmd in COMMAND_PRIORITY:
            for keyword in COMMANDS[cmd]:
                if keyword in text:
                    # Extract text after the keyword (useful for "شغل <song>")
                    parts = text.split(keyword, 1)
                    remaining = parts[1].strip() if len(parts) > 1 else ''
                    return cmd, remaining
        return None, ''

    async def _process_command(self, ctx, text: str):
        cmd, extra = self._match_command(text)
        if not cmd:
            return

        music = self.bot.get_cog('Music')
        vc = ctx.voice_client
        if not vc:
            return

        # ── STOP ──────────────────────────────────────────────────────────
        if cmd == 'stop':
            if music:
                player = music.get_player(ctx)
                player.queue.clear()
                player.current = None
                player.loop = False
            if vc.is_playing() or vc.is_paused():
                vc.stop()
            await ctx.send('**وقف** — Stopped playback and cleared queue.')

        # ── SKIP ──────────────────────────────────────────────────────────
        elif cmd == 'skip':
            if vc.is_playing() or vc.is_paused():
                vc.stop()  # triggers after callback → plays next in queue
                await ctx.send('**التالي** — Skipped.')
            else:
                await ctx.send('Nothing to skip.')

        # ── PAUSE ─────────────────────────────────────────────────────────
        elif cmd == 'pause':
            if vc.is_playing():
                vc.pause()
                await ctx.send('**توقف** — Paused.')

        # ── RESUME ────────────────────────────────────────────────────────
        elif cmd == 'resume':
            if vc.is_paused():
                vc.resume()
                await ctx.send('**كمل** — Resumed.')

        # ── PLAY ──────────────────────────────────────────────────────────
        elif cmd == 'play':
            # If paused, just resume
            if vc.is_paused():
                vc.resume()
                await ctx.send('**شغل** — Resumed.')
            # If extra text was said after "شغل", treat it as a search query
            elif extra and music:
                play_cmd = self.bot.get_command('play')
                if play_cmd:
                    await ctx.send(f'**شغل** — Searching for: *{extra}*')
                    await ctx.invoke(play_cmd, query=extra)

        # ── VOLUME UP ─────────────────────────────────────────────────────
        elif cmd == 'volume_up':
            if music:
                player = music.get_player(ctx)
                new_vol = min(1.0, player.volume + 0.2)
                player.volume = new_vol
                if vc.source:
                    vc.source.volume = new_vol
                await ctx.send(f'**ارفع** — Volume: {int(new_vol * 100)}%')

        # ── VOLUME DOWN ───────────────────────────────────────────────────
        elif cmd == 'volume_down':
            if music:
                player = music.get_player(ctx)
                new_vol = max(0.0, player.volume - 0.2)
                player.volume = new_vol
                if vc.source:
                    vc.source.volume = new_vol
                await ctx.send(f'**نزل** — Volume: {int(new_vol * 100)}%')


def setup(bot: commands.Bot):
    bot.add_cog(VoiceListener(bot))
