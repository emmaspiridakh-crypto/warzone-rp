"""
cogs/staff_activity.py
"""

from __future__ import annotations

import datetime

import discord
from discord import ui, app_commands
from discord.ext import commands

import config
from emojis import emoji
from utils import storage
from utils.components import build_base_container, add_separator, add_text, add_action_row

STORE_NAME = "staff_activity"

active_sessions: dict[int, datetime.datetime] = {}


def _fmt_duration(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if not h and not m:
        parts.append(f"{s}s")
    return " ".join(parts)


class StaffActivity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _log(self, guild: discord.Guild, member: discord.Member, *, joined: bool, duration_seconds: int | None = None):
        channel = guild.get_channel(config.STAFF_ACTIVITY_LOG_CHANNEL_ID)
        if not channel:
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        embed = discord.Embed(color=config.EMBED_COLOR, timestamp=now)
        if joined:
            embed.title = f"{emoji('staff_activity', 'on_duty')} On Duty - Join"
            embed.description = f"{member.mention} μπήκε on duty."
        else:
            embed.title = f"{emoji('staff_activity', 'off_duty')} On Duty - Leave"
            embed.description = f"{member.mention} βγήκε από on duty.\nΔιάρκεια: **{_fmt_duration(duration_seconds or 0)}**"
        embed.add_field(name="Ώρα", value=discord.utils.format_dt(now, style="F"))
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        target_id = config.STAFF_ACTIVITY_VOICE_CHANNEL_ID
        role = member.guild.get_role(config.ON_DUTY_ROLE_ID)

        if after.channel and after.channel.id == target_id and (not before.channel or before.channel.id != target_id):
            active_sessions[member.id] = datetime.datetime.now(datetime.timezone.utc)
            if role:
                await member.add_roles(role, reason="Staff Activity - on duty")
            await self._log(member.guild, member, joined=True)

        if before.channel and before.channel.id == target_id and (not after.channel or after.channel.id != target_id):
            start = active_sessions.pop(member.id, None)
            duration = 0
            if start:
                duration = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
            store = storage.get_store(STORE_NAME)
            store[str(member.id)] = store.get(str(member.id), 0) + duration
            storage.save(STORE_NAME, store)
            if role:
                await member.remove_roles(role, reason="Staff Activity - off duty")
            await self._log(member.guild, member, joined=False, duration_seconds=int(duration))

    # ---------------- Panel ----------------
    def _build_panel_view(self, guild: discord.Guild) -> ui.LayoutView:
        store = storage.get_store(STORE_NAME)
        totals = dict(store)
        now = datetime.datetime.now(datetime.timezone.utc)
        for uid, start in active_sessions.items():
            totals[str(uid)] = totals.get(str(uid), 0) + (now - start).total_seconds()

        ranking = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:10]
        lines = []
        for i, (uid, secs) in enumerate(ranking, start=1):
            member = guild.get_member(int(uid))
            name = member.mention if member else f"`{uid}`"
            lines.append(f"**#{i}** {name} — {_fmt_duration(secs)}")
        leaderboard_text = "\n".join(lines) if lines else "Δεν υπάρχουν δεδομένα ακόμα."

        on_duty_lines = []
        for uid in active_sessions:
            member = guild.get_member(uid)
            if member:
                on_duty_lines.append(f"{emoji('staff_activity', 'on_duty')} {member.mention}")
        on_duty_text = "\n".join(on_duty_lines) if on_duty_lines else "Κανείς δεν είναι on duty αυτή τη στιγμή."

        container = build_base_container(
            title="Staff Activity",
            description="Leaderboard χρόνου & live status. Μπες στο On Duty 1 για να ξεκινήσει ο χρόνος σου.",
            banner_url=config.STAFF_ACTIVITY_BANNER_URL,
        )
        add_separator(container)
        add_text(container, f"**{emoji('staff_activity', 'leaderboard')} Leaderboard**\n{leaderboard_text}")
        add_separator(container)
        add_text(container, f"**Live Status**\n{on_duty_text}")
        add_separator(container)
        refresh_btn = ui.Button(label="Refresh", style=discord.ButtonStyle.secondary,
                                 emoji="🔄", custom_id="staff_activity_refresh")
        add_action_row(container, refresh_btn)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view

    # FIX: CRITICAL — σπαστεί indentation στο original (await ήταν εκτός μεθόδου → SyntaxError)
    @app_commands.command(name="panel-staff-activity", description="Στέλνει το Staff Activity leaderboard panel")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID, config.MANAGER_ROLE_ID)
    async def panel_staff_activity(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        view = self._build_panel_view(interaction.guild)
        await interaction.channel.send(view=view)
        await interaction.followup.send("✅ Στάλθηκε.", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        if interaction.data.get("custom_id") == "staff_activity_refresh":
            view = self._build_panel_view(interaction.guild)
            # FIX: flags απαραίτητα για Components V2 στο edit_message
            await interaction.channel.send(view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffActivity(bot))
