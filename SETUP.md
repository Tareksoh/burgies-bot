# Discord Music Bot — Setup Guide

## Prerequisites

1. **Python 3.10+** — https://python.org/downloads
2. **FFmpeg** (required for audio) — https://ffmpeg.org/download.html
   - Windows: Download a build, extract it, and add the `bin/` folder to your system PATH
   - Or install via `winget install ffmpeg` in PowerShell

---

## Step 1 — Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **New Application**, give it a name
3. Go to **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent**
5. Copy your **Token** (keep this secret!)
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Connect`, `Speak`, `Send Messages`, `Embed Links`, `Read Message History`
7. Open the generated URL to invite the bot to your server

---

## Step 2 — Configure the Bot

```bash
copy .env.example .env
```

Edit `.env` and fill in:
- `DISCORD_TOKEN` — your bot token from Step 1
- `WHISPER_MODEL` — optional, defaults to `base` (options: tiny, base, small, medium, large-v3)
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` — optional, for Spotify links

---

## Step 3 — Install Dependencies

**Important:** If you previously installed `discord.py`, uninstall it first:
```bash
pip uninstall discord.py -y
```

Then install everything:
```bash
pip install -r requirements.txt
```

This installs **py-cord** (needed for voice receiving), **faster-whisper** (Arabic speech recognition), and other dependencies.

---

## Step 4 — Run the Bot

```bash
python bot.py
```

---

## Text Commands

| Command | Description |
|---|---|
| `!play <url or search>` | Play from YouTube, Spotify, SoundCloud, or search |
| `!pause` | Pause playback |
| `!resume` | Resume playback |
| `!skip` | Skip current song |
| `!stop` | Stop and clear queue |
| `!queue` | Show the queue |
| `!nowplaying` | Show current song |
| `!volume <0-100>` | Set volume |
| `!loop` | Toggle loop |
| `!shuffle` | Shuffle the queue |
| `!remove <#>` | Remove song from queue by number |
| `!clear` | Clear the queue |
| `!search <query>` | Search YouTube, show top 5 results |
| `!join` | Join your voice channel |
| `!leave` | Disconnect bot |
| `!listen` | Start listening for Arabic voice commands |
| `!stoplisten` | Stop voice listening |
| `!help` | Show all commands |

## Arabic Voice Commands (Khaleeji)

Type `!listen` to activate. Then say any of these in voice chat:

| Say | Action |
|---|---|
| **وقف** / **سكر** / **بس** / **خلاص** | Stop and clear queue |
| **غير** / **غيرها** / **التالي** | Skip to next song |
| **سكت** / **لحظة** / **استنى** | Pause |
| **كمل** / **رجع** / **استمر** | Resume |
| **شغل** / **حط** | Resume (or play a song if you say the name after) |
| **ارفع** / **زود** / **ارفع الصوت** | Volume up (+20%) |
| **نزل** / **خفف** / **نزل الصوت** | Volume down (-20%) |

You can also say **شغل** followed by a song name (e.g. "شغل ديسباسيتو") and the bot will search and play it.

## Supported Link Types

- **YouTube** — video URLs, playlist URLs
- **SoundCloud** — track and playlist URLs
- **Spotify** — track, album, and playlist URLs (requires Spotify credentials)
- **Plain text** — searches YouTube automatically

---

## Troubleshooting

- **"FFmpeg not found"** — Make sure FFmpeg is installed and on your PATH
- **"Opus not loaded"** — Install `PyNaCl`: `pip install PyNaCl`
- **Spotify not working** — Check your Client ID/Secret in `.env`
- **Bot not responding** — Make sure Message Content Intent is enabled in the Developer Portal
- **Voice commands not working** — Make sure you typed `!listen` first, and speak clearly
- **Whisper model slow** — Use `WHISPER_MODEL=tiny` in `.env` for faster (less accurate) results
- **"Cannot install py-cord"** — Run `pip uninstall discord.py -y` first, then install again
