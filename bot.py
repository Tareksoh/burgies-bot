import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '!')

if not TOKEN:
    raise ValueError('DISCORD_TOKEN is not set in your .env file')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'Prefix: {PREFIX}')
    print('Music bot is ready!')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening,
        name=f'{PREFIX}play | Music Bot'
    ))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'Missing argument: `{error.param.name}`. Use `{PREFIX}help` for usage.')
    else:
        await ctx.send(f'An error occurred: {str(error)}')


@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(title='Music Bot Commands', color=0x5865F2)
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    commands_list = {
        'Playback': [
            (f'`{PREFIX}play <url/query>`', 'Play from YouTube, Spotify, SoundCloud or search'),
            (f'`{PREFIX}pause`', 'Pause playback'),
            (f'`{PREFIX}resume`', 'Resume paused playback'),
            (f'`{PREFIX}skip`', 'Skip current song'),
            (f'`{PREFIX}stop`', 'Stop and clear the queue'),
            (f'`{PREFIX}volume <0-100>`', 'Set volume'),
        ],
        'Queue': [
            (f'`{PREFIX}queue`', 'Show the current queue'),
            (f'`{PREFIX}nowplaying`', 'Show currently playing song'),
            (f'`{PREFIX}shuffle`', 'Shuffle the queue'),
            (f'`{PREFIX}remove <index>`', 'Remove a song from queue'),
            (f'`{PREFIX}clear`', 'Clear the queue'),
            (f'`{PREFIX}loop`', 'Toggle loop for current song'),
        ],
        'Voice Control': [
            (f'`{PREFIX}listen`', 'Start listening for Arabic voice commands'),
            (f'`{PREFIX}stoplisten`', 'Stop listening for voice commands'),
        ],
        'Other': [
            (f'`{PREFIX}join`', 'Join your voice channel'),
            (f'`{PREFIX}leave`', 'Leave the voice channel'),
            (f'`{PREFIX}search <query>`', 'Search YouTube and show top 5 results'),
        ],
    }

    for category, cmds in commands_list.items():
        value = '\n'.join(f'{name} — {desc}' for name, desc in cmds)
        embed.add_field(name=category, value=value, inline=False)

    embed.set_footer(text='Supports YouTube, Spotify, SoundCloud + Arabic voice commands!')
    await ctx.send(embed=embed)


async def main():
    async with bot:
        bot.load_extension('music_cog')
        bot.load_extension('voice_listener')
        await bot.start(TOKEN)


asyncio.run(main())
