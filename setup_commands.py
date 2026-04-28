import discord
from discord import app_commands
import uuid
from translator import get_language_info
from database import (
    add_language, get_languages, add_channel_to_group,
    add_universal_channel, set_config, get_config,
    get_all_groups, get_channels_in_group
)

# Keywords that mark a channel as universal (visible to all languages)
UNIVERSAL_KEYWORDS = [
    "welcome", "rules", "announcements", "announce", "info",
    "information", "news", "updates", "start", "readme",
    "server-info", "important", "bots", "bot-commands"
]

def is_universal_channel(channel: discord.TextChannel) -> bool:
    name = channel.name.lower()
    return any(kw in name for kw in UNIVERSAL_KEYWORDS)

async def create_language_role(guild: discord.Guild, lang_code: str) -> discord.Role:
    """Create or retrieve the role for a language."""
    info = get_language_info(lang_code)
    role_name = f"{info['flag']} {info['name']} Speaker"
    existing = discord.utils.get(guild.roles, name=role_name)
    if existing:
        return existing
    role = await guild.create_role(name=role_name, mentionable=False)
    return role

async def set_channel_permissions(
    channel: discord.TextChannel,
    lang_roles: list[discord.Role],
    own_role: discord.Role,
    default_role: discord.Role,
    is_universal: bool = False
):
    """
    Set permissions on a language channel:
    - Universal channels: visible to everyone
    - Language channels: visible only to own_role (and hidden from default_role + other lang roles)
    """
    overwrites = {}

    if is_universal:
        overwrites[default_role] = discord.PermissionOverwrite(read_messages=True)
    else:
        # Hide from @everyone by default
        overwrites[default_role] = discord.PermissionOverwrite(read_messages=False)
        # Show to own language role
        overwrites[own_role] = discord.PermissionOverwrite(read_messages=True)
        # Explicitly hide from other language roles
        for role in lang_roles:
            if role.id != own_role.id:
                overwrites[role] = discord.PermissionOverwrite(read_messages=False)

    await channel.edit(overwrites=overwrites)

def make_lang_channel_name(base_name: str, lang_code: str) -> str:
    """Convert #general to #general-fr, preserving emojis."""
    # Strip leading emoji/special chars for suffix, keep them in place
    return f"{base_name}-{lang_code}"

async def run_setup(interaction: discord.Interaction, languages: list[str]):
    """
    Full server setup:
    1. Create language roles
    2. Scan existing channels
    3. Mark universal channels
    4. Clone channels per language
    5. Set permissions
    6. Create language picker channel
    """
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    default_role = guild.default_role  # @everyone

    status_messages = []

    # ââ Step 1: Create roles ââââââââââââââââââââââââââââââââââââââââââââââââââ
    lang_roles: dict[str, discord.Role] = {}
    for lang_code in languages:
        role = await create_language_role(guild, lang_code)
        lang_roles[lang_code] = role
        info = get_language_info(lang_code)
        add_language(lang_code, info["name"], info["flag"], role.id)
        status_messages.append(f"â Created role: {info['flag']} {info['name']} Speaker")

    all_roles = list(lang_roles.values())

    # ââ Step 2: Scan existing channels âââââââââââââââââââââââââââââââââââââââ
    text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
    universal = []
    to_clone = []

    for ch in text_channels:
        # Skip channels we already created (lang-suffixed)
        if any(ch.name.endswith(f"-{lang}") for lang in languages):
            continue
        if is_universal_channel(ch):
            universal.append(ch)
        else:
            to_clone.append(ch)

    # Mark universal channels
    for ch in universal:
        add_universal_channel(ch.id)
        await set_channel_permissions(ch, all_roles, None, default_role, is_universal=True)
        status_messages.append(f"ð Universal: #{ch.name}")

    # ââ Step 3: Clone channels per language âââââââââââââââââââââââââââââââââââ
    for ch in to_clone:
        group_id = str(uuid.uuid4())

        # Register the original channel as English (base language)
        base_lang = languages[0]  # First language = base (English)
        add_channel_to_group(group_id, ch.id, base_lang)
        await set_channel_permissions(
            ch, all_roles, lang_roles[base_lang], default_role
        )

        # Create copies for all other languages
        for lang_code in languages[1:]:
            new_name = make_lang_channel_name(ch.name, lang_code)
            info = get_language_info(lang_code)
            topic = f"{info['flag']} {info['name']} version of #{ch.name}"

            try:
                new_ch = await guild.create_text_channel(
                    name=new_name,
                    category=ch.category,
                    topic=topic,
                    position=ch.position + 1
                )
                await set_channel_permissions(
                    new_ch, all_roles, lang_roles[lang_code], default_role
                )
                add_channel_to_group(group_id, new_ch.id, lang_code)
                status_messages.append(f"â Created #{new_name}")
            except Exception as e:
                status_messages.append(f"â Failed to create #{new_name}: {e}")

    # ââ Step 4: Create language picker channel ââââââââââââââââââââââââââââââââ
    picker_ch = await guild.create_text_channel(
        name="ðã»pick-your-language",
        position=0
    )
    # Make picker visible to everyone
    await picker_ch.edit(overwrites={
        default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
    })
    set_config("picker_channel_id", str(picker_ch.id))
    add_universal_channel(picker_ch.id)

    await post_language_picker(picker_ch)
    status_messages.append(f"â Created language picker: #{picker_ch.name}")

    # ââ Step 5: Update @everyone so they default to English ââââââââââââââââââ
    # Hide all language channels from @everyone (already done above)
    # Give @everyone the English role by default via a welcome message instead
    set_config("default_lang", languages[0])
    set_config("setup_done", "true")

    summary = "\n".join(status_messages)
    await interaction.followup.send(
        f"**GUMPbot setup complete!**\n\n{summary}\n\n"
        f"New members will default to **{get_language_info(languages[0])['name']}** until they pick a language.",
        ephemeral=True
    )

async def post_language_picker(channel: discord.TextChannel):
    """Post or update the language picker message with buttons."""
    languages = get_languages()
    if not languages:
        return

    view = LanguagePickerView(languages)
    embed = discord.Embed(
        title="ð Choose Your Language",
        description="Click your native language below to see the server in your language.\n\nYou can change it anytime by clicking a different button.",
        color=0x5865F2
    )
    for lang in languages:
        embed.add_field(name=f"{lang['flag']} {lang['name']}", value="\u200b", inline=True)

    await channel.send(embed=embed, view=view)

class LanguagePickerView(discord.ui.View):
    def __init__(self, languages: list[dict]):
        super().__init__(timeout=None)
        for lang in languages:
            self.add_item(LanguageButton(lang))

class LanguageButton(discord.ui.Button):
    def __init__(self, lang: dict):
        super().__init__(
            label=f"{lang['flag']} {lang['name']}",
            custom_id=f"lang_{lang['code']}",
            style=discord.ButtonStyle.secondary
        )
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        languages = get_languages()

        # Remove all existing language roles
        lang_role_ids = {l["role_id"] for l in languages}
        roles_to_remove = [r for r in member.roles if r.id in lang_role_ids]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        # Assign selected language role
        new_role = guild.get_role(self.lang["role_id"])
        if new_role:
            await member.add_roles(new_role)

        await interaction.response.send_message(
            f"{self.lang['flag']} You'll now see the server in **{self.lang['name']}**!",
            ephemeral=True
        )

async def cmd_add_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Create language copies of a new channel."""
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    languages = get_languages()
    default_role = guild.default_role

    if not languages:
        await interaction.followup.send("Run /setup first.", ephemeral=True)
        return

    group_id = str(uuid.uuid4())
    base_lang = get_config("default_lang") or languages[0]["code"]

    all_roles = [guild.get_role(l["role_id"]) for l in languages]
    all_roles = [r for r in all_roles if r]

    base_role = guild.get_role(next(l["role_id"] for l in languages if l["code"] == base_lang))
    add_channel_to_group(group_id, channel.id, base_lang)
    await set_channel_permissions(channel, all_roles, base_role, default_role)

    created = []
    for lang in languages:
        if lang["code"] == base_lang:
            continue
        new_name = make_lang_channel_name(channel.name, lang["code"])
        role = guild.get_role(lang["role_id"])
        try:
            new_ch = await guild.create_text_channel(
                name=new_name,
                category=channel.category,
                position=channel.position + 1
            )
            await set_channel_permissions(new_ch, all_roles, role, default_role)
            add_channel_to_group(group_id, new_ch.id, lang["code"])
            created.append(f"â #{new_name}")
        except Exception as e:
            created.append(f"â #{new_name}: {e}")

    await interaction.followup.send(
        f"Channel group created for #{channel.name}:\n" + "\n".join(created),
        ephemeral=True
    )

async def cmd_add_language(interaction: discord.Interaction, lang_code: str):
    """Add a new language across all existing channel groups."""
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    default_role = guild.default_role
    lang_code = lang_code.lower().strip()
    info = get_language_info(lang_code)

    # Create role
    role = await create_language_role(guild, lang_code)
    add_language(lang_code, info["name"], info["flag"], role.id)

    all_languages = get_languages()
    all_roles = [guild.get_role(l["role_id"]) for l in all_languages]
    all_roles = [r for r in all_roles if r]

    created = []
    groups = get_all_groups()

    for group_id in groups:
        members = get_channels_in_group(group_id)
        # Find the base (English) channel to clone from
        base_lang = get_config("default_lang") or "en"
        base = next((m for m in members if m["language"] == base_lang), members[0] if members else None)
        if not base:
            continue

        base_ch = guild.get_channel(base["channel_id"])
        if not base_ch:
            continue

        new_name = make_lang_channel_name(base_ch.name, lang_code)
        try:
            new_ch = await guild.create_text_channel(
                name=new_name,
                category=base_ch.category,
                position=base_ch.position + 1,
                topic=f"{info['flag']} {info['name']} version of #{base_ch.name}"
            )
            await set_channel_permissions(new_ch, all_roles, role, default_role)
            add_channel_to_group(group_id, new_ch.id, lang_code)
            created.append(f"â #{new_name}")
        except Exception as e:
            created.append(f"â #{new_name}: {e}")

    # Update language picker
    picker_id = get_config("picker_channel_id")
    if picker_id:
        picker_ch = guild.get_channel(int(picker_id))
        if picker_ch:
            await picker_ch.purge(limit=10)
            await post_language_picker(picker_ch)

    await interaction.followup.send(
        f"{info['flag']} **{info['name']}** added!\n\n" + "\n".join(created),
        ephemeral=True
    )

async def cmd_cleanup(interaction: discord.Interaction):
    """
    Delete all language-suffixed channels and reset the database.
    Keeps all original channels intact.
    """
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    languages = get_languages()

    # Build list of known language suffixes
    lang_codes = [l["code"] for l in languages] if languages else []

    # Also catch common suffixes even if DB is empty
    # by scanning for any channel ending in -xx (2-letter code)
    import re
    suffix_pattern = re.compile(r'-[a-z]{2}(-[a-z]{2})*$')

    deleted = []
    skipped = []

    text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]

    for ch in text_channels:
        name = ch.name.lower()
        # Delete if name ends with a language suffix pattern like -fr, -ar, -fr-ar
        if suffix_pattern.search(name):
            try:
                await ch.delete(reason="GUMPbot cleanup")
                deleted.append(f"ðï¸ #{ch.name}")
            except discord.Forbidden:
                skipped.append(f"â ï¸ #{ch.name} (no permission)")
            except Exception as e:
                skipped.append(f"â #{ch.name}: {e}")

    # Also delete the language picker channel
    picker_id = get_config("picker_channel_id")
    if picker_id:
        picker_ch = guild.get_channel(int(picker_id))
        if picker_ch:
            try:
                await picker_ch.delete(reason="GUMPbot cleanup")
                deleted.append(f"ðï¸ #{picker_ch.name}")
            except Exception:
                pass

    # Reset the database
    import sqlite3
    from database import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM channel_groups")
    conn.execute("DELETE FROM universal_channels")
    conn.execute("DELETE FROM languages")
    conn.execute("DELETE FROM message_map")
    conn.execute("DELETE FROM config")
    conn.commit()
    conn.close()

    # Delete language roles
    for lang in languages:
        role = guild.get_role(lang["role_id"])
        if role:
            try:
                await role.delete(reason="GUMPbot cleanup")
                deleted.append(f"ðï¸ Role: {lang['flag']} {lang['name']} Speaker")
            except Exception:
                pass

    summary = "\n".join(deleted) if deleted else "Nothing to delete."
    if skipped:
        summary += "\n\n**Skipped:**\n" + "\n".join(skipped)

    await interaction.followup.send(
        f"**Cleanup complete!** Server reset to original channels.\n\n{summary}\n\n"
        f"Run `/setup languages:en,fr` when ready to set up again.",
        ephemeral=True
    )
