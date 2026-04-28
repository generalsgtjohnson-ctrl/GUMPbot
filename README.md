# GUMPbot 🌐

A Discord translation bot that mirrors messages between language channels in real time. Users pick their native language once and see the entire server in that language.

---

## How It Works

1. A new member joins → they default to English until they pick a language
2. They visit `#🌐・pick-your-language` and click their language
3. The server reorganizes — they only see channels in their language
4. When anyone posts in any channel, GUMPbot translates and mirrors it to all language versions automatically
5. Replies are threaded — responses stay in context across all languages

---

## Setup Guide

### Step 1 — Create a Discord Bot

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → name it **GUMPbot** → click **Create**
3. Go to the **Bot** tab
4. Click **Add Bot** → confirm
5. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent**
   - **Message Content Intent**
6. Click **Reset Token** → copy and save your token
7. Go to **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator` (needed for channel creation and permission management)
8. Copy the URL → open in browser → invite GUMPbot to your server

---

### Step 2 — Get a DeepL API Key

1. Go to [https://www.deepl.com/pro#developer](https://www.deepl.com/pro#developer)
2. Sign up for a **free account**
3. Go to your **Account** page → copy your **Authentication Key for DeepL API**

---

### Step 3 — Deploy to Railway

1. Create a free account at [https://railway.app](https://railway.app)
2. Create a new GitHub repository called `gumpbot`
3. Upload all the bot files to the repository (GitHub website → Add file → Upload files)
4. In Railway: **New Project → Deploy from GitHub repo** → select your repo
5. Go to your service → **Variables** → add:
   - `DISCORD_TOKEN` → your Discord bot token
   - `DEEPL_API_KEY` → your DeepL API key
6. Railway deploys automatically — GUMPbot comes online

---

### Step 4 — Run Setup in Discord

Once GUMPbot is online in your server, go to any channel and run:

```
/setup languages:en,fr
```

GUMPbot will:
- Create `🇬🇧 English Speaker` and `🇫🇷 French Speaker` roles
- Scan all your existing channels
- Auto-detect universal channels (welcome, rules, announcements, etc.) — these stay visible to everyone
- Clone every other channel into French (e.g. `🎮・gaming` → `🎮・gaming-fr`)
- Set permissions so each role only sees their language channels
- Create `#🌐・pick-your-language` with language buttons
- New members default to English automatically

---

## Commands

### `/setup languages:en,fr`
Run once to configure the entire server. Pass the language codes you want at launch.

### `/addchannel #channel-name`
Creates language copies of a new channel you've added, with correct permissions and mirroring set up automatically.

### `/addlanguage de`
Adds a new language across every channel in the server. Also updates the language picker with a new button.

---

## Adding a New Language Later

Just run `/addlanguage es` (or any language code). GUMPbot will:
- Create a `🇪🇸 Spanish Speaker` role
- Create `#channel-name-es` for every existing channel
- Set permissions on all of them
- Add a Spanish button to the language picker
- Start translating and mirroring immediately

---

## Supported Languages

| Code | Language    | Flag |
|------|-------------|------|
| en   | English     | 🇬🇧  |
| es   | Spanish     | 🇪🇸  |
| fr   | French      | 🇫🇷  |
| de   | German      | 🇩🇪  |
| it   | Italian     | 🇮🇹  |
| pt   | Portuguese  | 🇧🇷  |
| ja   | Japanese    | 🇯🇵  |
| ko   | Korean      | 🇰🇷  |
| zh   | Chinese     | 🇨🇳  |
| ru   | Russian     | 🇷🇺  |
| ar   | Arabic      | 🇸🇦  |
| nl   | Dutch       | 🇳🇱  |
| pl   | Polish      | 🇵🇱  |
| sv   | Swedish     | 🇸🇪  |
| tr   | Turkish     | 🇹🇷  |

---

## Universal Channel Auto-Detection

GUMPbot automatically keeps these channels visible to everyone (no language gating):

`welcome` `rules` `announcements` `announce` `info` `information` `news` `updates` `start` `readme` `server-info` `important` `bots` `bot-commands`

Any channel with these words in the name stays universal. The language picker channel is also always universal.

---

## File Structure

```
gumpbot/
├── bot.py               # Main bot — events, mirroring, slash commands
├── setup_commands.py    # /setup, /addchannel, /addlanguage logic
├── translator.py        # DeepL wrapper + language info
├── database.py          # SQLite — message maps, channel groups, languages
├── requirements.txt     # Python dependencies
├── Procfile             # Railway deployment
└── .gitignore
```

---

## Notes

- GUMPbot needs **Administrator** permission to create channels and manage permissions at scale
- The SQLite database stores message mappings for threading. On Railway's free tier it resets on restart — this only affects thread linking for old messages, new messages work fine
- DeepL free tier: 500,000 characters/month — sufficient for most active servers
- To change a channel pair config, you can re-run `/setup` (it will skip already-created channels) or use `/addchannel`
