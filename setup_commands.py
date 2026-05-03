import discord
from discord import app_commands
import uuid
import re
import sqlite3
from translator import get_language_info
from database import (
    add_language, get_languages, add_channel_to_group,
    add_universal_channel, set_config, get_config,
    get_all_groups, get_channels_in_group, reset_guild, DB_PATH
)

UNIVERSAL_KEYWORDS = [
    "welcome", "rules", "announcements", "announce", "info",
    "information", "news", "updates", "start", "readme",
    "server-info", "important", "bots", "bot-commands"
]

def is_universal_channel(channel: discord.TextChannel) -> bool:
    name = channel.name.lower()
    return any(kw in name for kw in UNIVERSAL_KEYWORDS)

async def create_language_role(guild: discord.Guild, lang_code: str) -> discord.Role:
    info = get_language_info(lang_code)
    role_name = f"{info['flag']} {info['name']} Speaker"
    existing = discord.utils.get(guild.roles, name=role_name)
    if existing:
        return existing
    return await guild.create_role(name=role_name, mentionable=False)

def make_lang_channel_name(base_name: str, lang_code: str) -> str:
    return f"{base_name}-{lang_code}"

async def post_language_picker(channel: discord.TextChannel, guild_id: int):
    languages = get_languages(guild_id)
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
        languages = get_languages(guild.id)
        lang_role_ids = {l["role_id"] for l in languages}
        roles_to_remove = [r for r in member.roles if r.id in lang_role_ids]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
        new_role = guild.get_role(self.lang["role_id"])
        if new_role:
            await member.add_roles(new_role)
        await interaction.response.send_message(
            f"{self.lang['flag']} You'll now see the server in **{self.lang['name']}**!",
            ephemeral=True
        )

async def run_setup(interaction: discord.Interaction, languages: list[str]):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    guild_id = guild.id
    default_role = guild.default_role
    status_messages = []

    # Step 1: Create roles
    lang_roles: dict[str, discord.Role] = {}
    for lang_code in languages:
        role = await create_language_role(guild, lang_code)
        lang_roles[lang_code] = role
        info = get_language_info(lang_code)
        add_language(guild_id, lang_code, info["name"], info["flag"], role.id)
        status_messages.append(f"â Role: {info['flag']} {info['name']} Speaker")

    all_roles = list(lang_roles.values())

    # Step 2: Scan channels
    text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
    universal = []
    to_clone = []

    for ch in text_channels:
        if any(ch.name.endswith(f"-{lang}") for lang in languages):
            continue
        if is_universal_channel(ch):
            universal.append(ch)
        else:
            to_clone.append(ch)

    # Step 3: Mark universal channels
    for ch in universal:
        add_universal_channel(guild_id, ch.id)
        overwrites = dict(ch.overwrites)
        overwrites[default_role] = discord.PermissionOverwrite(read_messages=True)
        await ch.edit(overwrites=overwrites)
        status_messages.append(f"ð Universal: #{ch.name}")

    # Step 4: Clone channels
    for ch in to_clone:
        group_id = str(uuid.uuid4())
        base_lang = languages[0]

        # Set permissions on original (base language) channel
        base_overwrites = dict(ch.overwrites)
        base_overwrites[default_role] = discord.PermissionOverwrite(read_messages=False)
        base_overwrites[lang_roles[base_lang]] = discord.PermissionOverwrite(read_messages=True)
        for lr_code, lr in lang_roles.items():
            if lr_code != base_lang:
                base_overwrites[lr] = discord.PermissionOverwrite(read_messages=False)
        await ch.edit(overwrites=base_overwrites)
        add_channel_to_group(guild_id, group_id, ch.id, base_lang)

        # Create language copies
        for lang_code in languages[1:]:
            new_name = make_lang_channel_name(ch.name, lang_code)
            info = get_language_info(lang_code)

            lang_overwrites = dict(ch.overwrites)
            lang_overwrites[default_role] = discord.PermissionOverwrite(read_messages=False)
            lang_overwrites[lang_roles[lang_code]] = discord.PermissionOverwrite(read_messages=True)
            for lr_code, lr in lang_roles.items():
                if lr_code != lang_code:
                    lang_overwrites[lr] = discord.PermissionOverwrite(read_messages=False)

            try:
                new_ch = await guild.create_text_channel(
                    name=new_name,
                    category=ch.category,
                    topic=f"{info['flag']} {info['name']} version of #{ch.name}",
                    position=ch.position + 1,
                    overwrites=lang_overwrites
                )
                add_channel_to_group(guild_id, group_id, new_ch.id, lang_code)
                status_messages.append(f"â #{new_name}")
            except Exception as e:
                status_messages.append(f"â #{new_name}: {e}")

    # Step 5: Create language picker
    picker_ch = await guild.create_text_channel(
        name="ðã»pick-your-language",
        position=0,
        overwrites={default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)}
    )
    set_config(guild_id, "picker_channel_id", str(picker_ch.id))
    set_config(guild_id, "default_lang", languages[0])
    set_config(guild_id, "setup_done", "true")
    add_universal_channel(guild_id, picker_ch.id)
    await post_language_picker(picker_ch, guild_id)
    status_messages.append(f"â Language picker created")

    # Truncate if too long for Discord
    summary = "\n".join(status_messages)
    if len(summary) > 1800:
        summary = summary[:1800] + "\n... (truncated)"

    await interaction.followup.send(
        f"**GUMPbot setup complete!**\n\n{summary}\n\n"
        f"New members default to **{get_language_info(languages[0])['name']}**.",
        ephemeral=True
    )

async def cmd_add_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    guild_id = guild.id
    languages = get_languages(guild_id)
    default_role = guild.default_role

    if not languages:
        await interaction.followup.send("Run /setup first.", ephemeral=True)
        return

    group_id = str(uuid.uuid4())
    base_lang = get_config(guild_id, "default_lang") or languages[0]["code"]
    lang_roles = {l["code"]: guild.get_role(l["role_id"]) for l in languages}

    base_overwrites = dict(channel.overwrites)
    base_overwrites[default_role] = discord.PermissionOverwrite(read_messages=False)
    base_overwrites[lang_roles[base_lang]] = discord.PermissionOverwrite(read_messages=True)
    for lc, lr in lang_roles.items():
        if lc != base_lang:
            base_overwrites[lr] = discord.PermissionOverwrite(read_messages=False)
    await channel.edit(overwrites=base_overwrites)
    add_channel_to_group(guild_id, group_id, channel.id, base_lang)

    created = []
    for lang in languages:
        if lang["code"] == base_lang:
            continue
        new_name = make_lang_channel_name(channel.name, lang["code"])
        role = lang_roles[lang["code"]]
        lang_overwrites = dict(channel.overwrites)
        lang_overwrites[default_role] = discord.PermissionOverwrite(read_messages=False)
        lang_overwrites[role] = discord.PermissionOverwrite(read_messages=True)
        for lc, lr in lang_roles.items():
            if lc != lang["code"]:
                lang_overwrites[lr] = discord.PermissionOverwrite(read_messages=False)
        try:
            new_ch = await guild.create_text_channel(
                name=new_name,
                category=channel.category,
                position=channel.position + 1,
                overwrites=lang_overwrites
            )
            add_channel_to_group(guild_id, group_id, new_ch.id, lang["code"])
            created.append(f"â #{new_name}")
        except Exception as e:
            created.append(f"â #{new_name}: {e}")

    await interaction.followup.send(
        f"Channel group created for #{channel.name}:\n" + "\n".join(created),
        ephemeral=True
    )

async def cmd_add_language(interaction: discord.Interaction, lang_code: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    guild_id = guild.id
    default_role = guild.default_role
    lang_code = lang_code.lower().strip()
    info = get_language_info(lang_code)

    role = await create_language_role(guild, lang_code)
    add_language(guild_id, lang_code, info["name"], info["flag"], role.id)

    all_languages = get_languages(guild_id)
    lang_roles = {l["code"]: guild.get_role(l["role_id"]) for l in all_languages}

    created = []
    groups = get_all_groups(guild_id)
    base_lang = get_config(guild_id, "default_lang") or "en"

    for group_id in groups:
        members = get_channels_in_group(group_id)
        base = next((m for m in members if m["language"] == base_lang), members[0] if members else None)
        if not base:
            continue
        base_ch = guild.get_channel(base["channel_id"])
        if not base_ch:
            continue

        new_name = make_lang_channel_name(base_ch.name, lang_code)
        lang_overwrites = dict(base_ch.overwrites)
        lang_overwrites[default_role] = discord.PermissionOverwrite(read_messages=False)
        lang_overwrites[role] = discord.PermissionOverwrite(read_messages=True)
        for lc, lr in lang_roles.items():
            if lc != lang_code and lr:
                lang_overwrites[lr] = discord.PermissionOverwrite(read_messages=False)

        try:
            new_ch = await guild.create_text_channel(
                name=new_name,
                category=base_ch.category,
                position=base_ch.position + 1,
                topic=f"{info['flag']} {info['name']} version of #{base_ch.name}",
                overwrites=lang_overwrites
            )
            add_channel_to_group(guild_id, group_id, new_ch.id, lang_code)
            created.append(f"â #{new_name}")
        except Exception as e:
            created.append(f"â #{new_name}: {e}")

    # Update picker
    picker_id = get_config(guild_id, "picker_channel_id")
    if picker_id:
        picker_ch = guild.get_channel(int(picker_id))
        if picker_ch:
            await picker_ch.purge(limit=10)
            await post_language_picker(picker_ch, guild_id)

    summary = "\n".join(created)
    if len(summary) > 1800:
        summary = summary[:1800] + "\n... (truncated)"

    await interaction.followup.send(
        f"{info['flag']} **{info['name']}** added!\n\n{summary}",
        ephemeral=True
    )

async def cmd_cleanup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    guild_id = guild.id
    languages = get_languages(guild_id)
    suffix_pattern = re.compile(r'-[a-z]{2}(-[a-z]{2})*$')

    deleted = []
    skipped = []

    text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
    for ch in text_channels:
        if suffix_pattern.search(ch.name.lower()):
            try:
                await ch.delete(reason="GUMPbot cleanup")
                deleted.append(f"ðï¸ #{ch.name}")
            except discord.Forbidden:
                skipped.append(f"â ï¸ #{ch.name}")
            except Exception as e:
                skipped.append(f"â #{ch.name}: {e}")

    # Delete picker channel
    picker_id = get_config(guild_id, "picker_channel_id")
    if picker_id:
        picker_ch = guild.get_channel(int(picker_id))
        if picker_ch:
            try:
                await picker_ch.delete(reason="GUMPbot cleanup")
                deleted.append(f"ðï¸ #{picker_ch.name}")
            except Exception:
                pass

    # Reset DB for this guild only
    reset_guild(guild_id)

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
    if len(summary) > 1800:
        summary = summary[:1800] + "\n..."

    await interaction.followup.send(
        f"**Cleanup complete!**\n\n{summary}\n\nRun `/setup languages:en,fr,es,ar` to set up again.",
        ephemeral=True
    )
