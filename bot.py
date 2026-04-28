import discord
from discord import app_commands
import os

from database import init_db, get_group_for_channel, get_channels_in_group, \
    is_mirrored_message, save_mapping, get_mirrors, is_universal, \
    get_languages, get_config, get_language_by_role
from translator import Translator, get_language_info
from setup_commands import (
    run_setup, cmd_add_channel, cmd_add_language, LanguagePickerView, get_languages
)

# ── Discord setup ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class GUMPBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = GUMPBot()
translator = Translator()

# ── Slash commands ────────────────────────────────────────────────────────────

@client.tree.command(name="setup", description="Set up GUMPbot — clone channels and configure languages")
@app_commands.describe(languages="Comma-separated language codes, e.g: en,fr,es")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction, languages: str = "en,fr"):
    lang_list = [l.strip().lower() for l in languages.split(",") if l.strip()]
    if not lang_list:
        await interaction.response.send_message("Please provide at least one language code.", ephemeral=True)
        return
    await run_setup(interaction, lang_list)

@client.tree.command(name="addchannel", description="Create language copies of an existing channel")
@app_commands.describe(channel="The channel to clone into all languages")
@app_commands.checks.has_permissions(administrator=True)
async def addchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    await cmd_add_channel(interaction, channel)

@client.tree.command(name="addlanguage", description="Add a new language across all channels")
@app_commands.describe(language="Language code to add, e.g: de, ja, es")
@app_commands.checks.has_permissions(administrator=True)
async def addlanguage(interaction: discord.Interaction, language: str):
    await cmd_add_language(interaction, language)

# ── Events ────────────────────────────────────────────────────────────────────

@client.event
async def on_ready():
    init_db()
    # Re-register persistent language picker views so buttons work after restart
    languages = get_languages()
    if languages:
        client.add_view(LanguagePickerView(languages))

    print(f"[GUMPbot] Online as {client.user} ({client.user.id})")

@client.event
async def on_member_join(member: discord.Member):
    """Assign default language role to new members."""
    default_lang = get_config("default_lang") or "en"
    languages = get_languages()
    default = next((l for l in languages if l["code"] == default_lang), None)
    if default:
        role = member.guild.get_role(default["role_id"])
        if role:
            await member.add_roles(role)

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if not message.content or not message.content.strip():
        return
    if is_universal(message.channel.id):
        return

    group_id = get_group_for_channel(message.channel.id)
    if not group_id:
        return

    if is_mirrored_message(message.channel.id, message.id):
        return

    siblings = get_channels_in_group(group_id)
    source_lang = next(
        (s["language"] for s in siblings if s["channel_id"] == message.channel.id), None
    )
    if not source_lang:
        return

    # Determine if this is a reply
    reply_to_id = None
    if message.reference and message.reference.message_id:
        reply_to_id = message.reference.message_id

    src_info = get_language_info(source_lang)

    for sibling in siblings:
        if sibling["channel_id"] == message.channel.id:
            continue

        target_ch = client.get_channel(sibling["channel_id"])
        if not target_ch:
            continue

        target_lang = sibling["language"]
        tgt_info = get_language_info(target_lang)

        translated = translator.translate(message.content, target_lang)
        formatted = (
            f"{src_info['flag']}→{tgt_info['flag']} "
            f"**{message.author.display_name}:** {translated}"
        )

        try:
            sent = None
            if reply_to_id:
                mirrors = get_mirrors(message.channel.id, reply_to_id)
                parent_id = next((mid for (cid, mid) in mirrors if cid == sibling["channel_id"]), None)
                if parent_id:
                    try:
                        parent_msg = await target_ch.fetch_message(parent_id)
                        sent = await parent_msg.reply(formatted)
                    except discord.NotFound:
                        pass

            if not sent:
                sent = await target_ch.send(formatted)

            save_mapping(message.channel.id, message.id, sibling["channel_id"], sent.id)

        except discord.Forbidden:
            print(f"[GUMPbot] No permission to send in {sibling['channel_id']}")
        except Exception as e:
            print(f"[GUMPbot] Mirror error: {e}")

# ── Run ───────────────────────────────────────────────────────────────────────
token = os.environ.get("DISCORD_TOKEN")
if not token:
    raise ValueError("DISCORD_TOKEN environment variable not set.")

client.run(token)
