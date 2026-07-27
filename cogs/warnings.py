"""
cogs/warnings.py
------------------
Warning System (Ownership only).

/warn
    1. Ανοίγει Components V2 panel -> επιλογή χρήστη (UserSelect)
    2. Επιλογή επιπέδου warning 1-3 (εμφανίζει αν έχει ήδη άλλα ενεργά warnings)
    3. Modal για το reason
    4. Αποθηκεύεται το warning, μπαίνει ο ανάλογος ρόλος (WARN_ROLE_<level>_ID)
       στον χρήστη, στέλνεται DM στον χρήστη και log στο LOG_WARN_CHANNEL_ID.

/remove-warning <user>
    Ανοίγει panel με λίστα από τα ενεργά warnings του χρήστη (Select) ->
    αφαιρεί το επιλεγμένο, αφαιρεί τον ρόλο (αν δεν έχει άλλο warning ίδιου
    επιπέδου) και στέλνει log.

Persistence: JSON store (utils/storage.py) -> data/warnings.json
    { "<user_id>": [ {id, guild_id, level, reason, moderator_id, timestamp}, ... ] }
"""

from __future__ import annotations

import datetime
import uuid

import discord
from discord import ui, app_commands
from discord.ext import commands

import config
from utils import storage

STORE_NAME = "warnings"  # data/warnings.json

WARN_ROLE_IDS = {
    1: config.WARN_ROLE_1_ID,
    2: config.WARN_ROLE_2_ID,
    3: config.WARN_ROLE_3_ID,
}


# =========================================================
# Storage helpers
# =========================================================
def _get_warnings(user_id: int, guild_id: int) -> list[dict]:
    store = storage.get_store(STORE_NAME)
    return [w for w in store.get(str(user_id), []) if w.get("guild_id") == guild_id]


def _add_warning(user_id: int, guild_id: int, *, level: int, reason: str, moderator_id: int) -> dict:
    store = storage.get_store(STORE_NAME)
    user_warnings = store.setdefault(str(user_id), [])
    record = {
        "id": uuid.uuid4().hex[:8],
        "guild_id": guild_id,
        "level": level,
        "reason": reason,
        "moderator_id": moderator_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).timestamp(),
    }
    user_warnings.append(record)
    storage.save(STORE_NAME, store)
    return record


def _remove_warning(user_id: int, guild_id: int, warning_id: str) -> dict | None:
    store = storage.get_store(STORE_NAME)
    user_warnings = store.get(str(user_id), [])
    removed = next((w for w in user_warnings if w["id"] == warning_id and w.get("guild_id") == guild_id), None)
    if removed:
        user_warnings.remove(removed)
        store[str(user_id)] = user_warnings
        storage.save(STORE_NAME, store)
    return removed


# =========================================================
# Log helpers
# =========================================================
def _log_embed(guild: discord.Guild, *, title: str, color: int, fields: list[tuple[str, str, bool]]) -> discord.Embed:
    embed = discord.Embed(title=title, color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))
    for name, value, inline in fields:
        embed.add_field(name=name, value=value, inline=inline)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


async def _send_log(guild: discord.Guild, embed: discord.Embed):
    channel = guild.get_channel(config.LOG_WARN_CHANNEL_ID)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


def _announce_warn_embed(guild: discord.Guild, *, target: discord.Member, moderator: discord.Member,
                          level: int, reason: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚠️ Νέο Warning",
        description=f"Ο {target.mention} πήρε warning από τον {moderator.mention}",
        color=0xFEE75C,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Level", value=f"Warning {level}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    return embed


def _announce_remove_embed(guild: discord.Guild, *, target: discord.Member, moderator: discord.Member,
                            level: int) -> discord.Embed:
    embed = discord.Embed(
        title="✅ Αφαίρεση Warning",
        description=f"Αφαιρέθηκε warning από τον {target.mention} από τον {moderator.mention}",
        color=0x57F287,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Level", value=f"Warning {level}", inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    return embed


async def _send_announce(guild: discord.Guild, embed: discord.Embed):
    channel = guild.get_channel(config.WARN_ANNOUNCE_CHANNEL_ID)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


def _simple_view(text: str, color: discord.Colour) -> ui.LayoutView:
    container = ui.Container(accent_colour=color)
    container.add_item(ui.TextDisplay(text))
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


# =========================================================
# /warn — Βήμα 3: Modal για το reason
# =========================================================
class WarnReasonModal(ui.Modal, title="Λόγος Warning"):
    reason = ui.TextInput(
        label="Reason", style=discord.TextStyle.paragraph, max_length=500, required=True,
        placeholder="Γράψε τον λόγο του warning...",
    )

    def __init__(self, cog: "Warnings", target: discord.Member, level: int):
        super().__init__()
        self.cog = cog
        self.target = target
        self.level = level

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.finalize_warn(interaction, self.target, self.level, str(self.reason))


# =========================================================
# /warn — Βήμα 2: επιλογή επιπέδου
# =========================================================
class WarnLevelSelect(ui.Select):
    def __init__(self, cog: "Warnings", target: discord.Member):
        options = [
            discord.SelectOption(label="Warning 1", value="1", emoji="🟡"),
            discord.SelectOption(label="Warning 2", value="2", emoji="🟠"),
            discord.SelectOption(label="Warning 3", value="3", emoji="🔴"),
        ]
        super().__init__(placeholder="Επίλεξε επίπεδο warning...", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.target = target

    async def callback(self, interaction: discord.Interaction):
        level = int(self.values[0])
        await interaction.response.send_modal(WarnReasonModal(self.cog, self.target, level))


class WarnLevelView(ui.LayoutView):
    def __init__(self, cog: "Warnings", target: discord.Member, existing: list[dict]):
        super().__init__(timeout=180)
        container = ui.Container(accent_colour=discord.Colour.orange())

        if existing:
            lines = "\n".join(f"> `#{w['id']}` — Level **{w['level']}** — {w['reason'][:60]}" for w in existing[:5])
            existing_text = f"⚠️ Έχει ήδη **{len(existing)}** ενεργό/ά warning(s):\n{lines}"
        else:
            existing_text = "✅ Δεν έχει άλλα ενεργά warnings."

        container.add_item(ui.TextDisplay(
            f"## ⚠️ Warning System\n**Χρήστης:** {target.mention}\n\n{existing_text}\n\n"
            f"Επίλεξε το επίπεδο του warning:"
        ))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        row = ui.ActionRow()
        row.add_item(WarnLevelSelect(cog, target))
        container.add_item(row)
        self.add_item(container)


# =========================================================
# /warn — Βήμα 1: επιλογή χρήστη
# =========================================================
class WarnUserSelect(ui.UserSelect):
    def __init__(self, cog: "Warnings"):
        super().__init__(placeholder="Επίλεξε τον χρήστη που θες να δώσεις warning...", min_values=1, max_values=1)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        raw = self.values[0]
        target = interaction.guild.get_member(raw.id)
        if target is None:
            await interaction.response.send_message("⚠️ Δεν βρέθηκε ο χρήστης στο server.", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("⚠️ Δεν μπορείς να κάνεις warn τα bot βλακα.", ephemeral=True)
            return

        existing = _get_warnings(target.id, interaction.guild.id)
        await interaction.response.edit_message(view=WarnLevelView(self.cog, target, existing))


class WarnUserSelectView(ui.LayoutView):
    def __init__(self, cog: "Warnings"):
        super().__init__(timeout=180)
        container = ui.Container(accent_colour=discord.Colour.orange())
        container.add_item(ui.TextDisplay("## ⚠️ Warning System\nΕπίλεξε τον χρήστη που θέλεις του δώσεις warning:"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        row = ui.ActionRow()
        row.add_item(WarnUserSelect(cog))
        container.add_item(row)
        self.add_item(container)


# =========================================================
# /remove-warning — επιλογή ποιο warning θα αφαιρεθεί
# =========================================================
class RemoveWarningSelect(ui.Select):
    def __init__(self, cog: "Warnings", target: discord.Member, warnings_list: list[dict]):
        options = [
            discord.SelectOption(
                label=f"#{w['id']} — Level {w['level']}",
                value=w["id"],
                description=(w["reason"][:95] if w["reason"] else "—"),
            )
            for w in warnings_list[:25]
        ]
        super().__init__(placeholder="Επίλεξε ποιο warning να αφαιρεθεί...", min_values=1, max_values=1, options=options)
        self.cog = cog
        self.target = target

    async def callback(self, interaction: discord.Interaction):
        await self.cog.finalize_remove(interaction, self.target, self.values[0])


class RemoveWarningView(ui.LayoutView):
    def __init__(self, cog: "Warnings", target: discord.Member, warnings_list: list[dict]):
        super().__init__(timeout=180)
        container = ui.Container(accent_colour=discord.Colour.red())
        lines = "\n".join(f"> `#{w['id']}` — Level **{w['level']}** — {w['reason'][:60]}" for w in warnings_list[:10])
        container.add_item(ui.TextDisplay(
            f"## 🗑️ Remove Warning\n**Χρήστης:** {target.mention}\n\n{lines}\n\n"
            f"Επίλεξε ποιο warning θέλεις να αφαιρέσεις:"
        ))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        row = ui.ActionRow()
        row.add_item(RemoveWarningSelect(cog, target, warnings_list))
        container.add_item(row)
        self.add_item(container)


# =========================================================
# Main Cog
# =========================================================
class Warnings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------
    # /warn ολοκλήρωση
    # ---------------------------------------------------
    async def finalize_warn(self, interaction: discord.Interaction, target: discord.Member, level: int, reason: str):
        guild = interaction.guild
        moderator = interaction.user

        record = _add_warning(target.id, guild.id, level=level, reason=reason, moderator_id=moderator.id)

        role_note = ""
        role_id = WARN_ROLE_IDS.get(level)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await target.add_roles(role, reason=f"Warning level {level} by {moderator} (#{record['id']})")
                    role_note = f"\n✅ Προστέθηκε ο ρόλος {role.mention}"
                except discord.Forbidden:
                    role_note = "\n⚠️ Δεν προστέθηκε το role (λείπουν permissions)."
            else:
                role_note = "\n⚠️ Δεν βρέθηκε ο ρόλος για αυτό το level."

        total = len(_get_warnings(target.id, guild.id))

        await interaction.response.edit_message(view=_simple_view(
            f"## ✅ Warning Καταγράφτηκε\n"
            f"**Χρήστης:** {target.mention}\n**Level:** {level}\n**Reason:** {reason}\n"
            f"**Moderator:** {moderator.mention}\n**Σύνολο warnings:** {total}{role_note}",
            discord.Colour.green(),
        ))

        try:
            await target.send(f"⚠️ Έλαβες **Warning Level {level}** στον **{guild.name}**.\n**Λόγος:** {reason}")
        except discord.Forbidden:
            pass

        await _send_log(guild, _log_embed(
            guild, title="⚠️ Member Warned", color=0xFEE75C,
            fields=[
                ("Χρήστης", f"{target.mention} (`{target.id}`)", False),
                ("Warning ID", f"`#{record['id']}`", True),
                ("Level", str(level), True),
                ("Σύνολο Warnings", str(total), True),
                ("Moderator", f"{moderator.mention} (`{moderator.id}`)", False),
                ("Reason", reason, False),
            ],
        ))

        await _send_announce(guild, _announce_warn_embed(
            guild, target=target, moderator=moderator, level=level, reason=reason,
        ))

    # ---------------------------------------------------
    # /remove-warning ολοκλήρωση
    # ---------------------------------------------------
    async def finalize_remove(self, interaction: discord.Interaction, target: discord.Member, warning_id: str):
        guild = interaction.guild
        removed = _remove_warning(target.id, guild.id, warning_id)
        if not removed:
            await interaction.response.edit_message(view=_simple_view(
                "❌ Αυτό το warning δεν υπάρχει πια (ίσως αφαιρέθηκε ήδη).", discord.Colour.red(),
            ))
            return

        remaining = _get_warnings(target.id, guild.id)
        level = removed["level"]
        role_note = ""
        role_id = WARN_ROLE_IDS.get(level)
        if role_id and not any(w["level"] == level for w in remaining):
            role = guild.get_role(role_id)
            if role and role in target.roles:
                try:
                    await target.remove_roles(role, reason=f"Warning #{warning_id} removed by {interaction.user}")
                    role_note = f"\n✅ Αφαιρέθηκε ο ρόλος {role.mention}"
                except discord.Forbidden:
                    role_note = "\n⚠️ Δεν αφαιρέθηκε το role (λείπουν permissions)."

        await interaction.response.edit_message(view=_simple_view(
            f"## ✅ Warning Αφαιρέθηκε\n**Χρήστης:** {target.mention}\n**ID:** `#{warning_id}`\n"
            f"**Level:** {level}\n**Υπόλοιπα warnings:** {len(remaining)}{role_note}",
            discord.Colour.green(),
        ))

        await _send_log(guild, _log_embed(
            guild, title="🗑️ Warning Removed", color=0x57F287,
            fields=[
                ("Χρήστης", f"{target.mention} (`{target.id}`)", False),
                ("Warning ID", f"`#{warning_id}`", True),
                ("Level", str(level), True),
                ("Υπόλοιπα Warnings", str(len(remaining)), True),
                ("Αφαιρέθηκε από", f"{interaction.user.mention} (`{interaction.user.id}`)", False),
            ],
        ))

        await _send_announce(guild, _announce_remove_embed(
            guild, target=target, moderator=interaction.user, level=level,
        ))

    # ---------------------------------------------------
    # Slash Commands (Ownership only)
    # ---------------------------------------------------
    @app_commands.command(name="warn", description="Ανοίγει το warning panel")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID)
    async def warn_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=WarnUserSelectView(self), ephemeral=True)

    @app_commands.command(name="remove-warning", description="Αφαιρεί ένα warning από έναν χρήστη")
    @app_commands.describe(user="Ο χρήστης από τον οποίο θα αφαιρεθεί το warning")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID)
    async def remove_warning_cmd(self, interaction: discord.Interaction, user: discord.Member):
        existing = _get_warnings(user.id, interaction.guild.id)
        if not existing:
            await interaction.response.send_message(f"✅ Ο {user.mention} δεν έχει κανένα ενεργό warning.", ephemeral=True)
            return
        await interaction.response.send_message(view=RemoveWarningView(self, user, existing), ephemeral=True)

    # ---------------------------------------------------
    # Error handling (permission checks)
    # ---------------------------------------------------
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingAnyRole):
            msg = "⛔ Μόνο το Ownership μπορεί να χρησιμοποιήσει αυτή την εντολή."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Warnings(bot))
