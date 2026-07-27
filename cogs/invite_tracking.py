"""
cogs/invite_tracking.py
--------------------------
Invite tracking: ποιος προσκάλεσε ποιον, πόσα invites έχει συνολικά ο καθένας,
πόσα από τα άτομα που προσκάλεσε είναι ακόμα μέσα, και πόσα έχουν φύγει.

Πώς δουλεύει:
  1. Κρατάμε σε memory cache τα invites του server (code -> uses) ανά guild,
     συμπεριλαμβανομένου του vanity URL αν υπάρχει.
  2. Όταν μπαίνει νέο μέλος, συγκρίνουμε τα νέα invites με το cache για να
     βρούμε ποιο invite χρησιμοποιήθηκε (αυτό με αυξημένο uses· αν λείπει
     -> best effort έλεγχος στα audit logs, μάλλον ήταν single-use invite).
  3. Αποθηκεύουμε ποιος προσκάλεσε ποιον (data/invite_attribution.json) και
     τα στατιστικά ανά inviter (data/invite_stats.json).
  4. Όταν φύγει κάποιος, αν βρούμε ποιος τον προσκάλεσε, ενημερώνουμε τα
     στατιστικά (μετακινείται από "joined" σε "left") και κάνουμε log.

ΑΠΑΡΑΙΤΗΤΟ permission για το bot: Manage Server (να μπορεί να δει τα invites
του server μέσω guild.invites()).
"""

from __future__ import annotations

import discord
from discord import app_commands, ui
from discord.ext import commands

import config
from emojis import emoji
from utils import storage
from utils.permissions import member_has_any_role

STATS_STORE = "invite_stats"              # {inviter_id: {"total": int, "joined_ids": [...], "left_ids": [...]}}
ATTRIBUTION_STORE = "invite_attribution"  # {member_id: inviter_id | "vanity" | "unknown"}

# guild_id -> {code: uses}  (το "__vanity__" κρατάει το uses του vanity invite αν υπάρχει)
_invite_cache: dict[int, dict[str, int]] = {}


async def _snapshot(guild: discord.Guild) -> dict[str, int]:
    data: dict[str, int] = {}
    try:
        invites = await guild.invites()
        data.update({inv.code: inv.uses or 0 for inv in invites})
    except (discord.Forbidden, discord.HTTPException):
        pass
    try:
        vanity = await guild.vanity_invite()
        if vanity:
            data["__vanity__"] = vanity.uses or 0
    except (discord.Forbidden, discord.HTTPException):
        pass
    return data


def _stats_entry(stats: dict, inviter_key: str) -> dict:
    return stats.setdefault(inviter_key, {"total": 0, "joined_ids": [], "left_ids": []})


class InviteTracking(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        for guild in self.bot.guilds:
            _invite_cache[guild.id] = await _snapshot(guild)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            _invite_cache[guild.id] = await _snapshot(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        _invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        _invite_cache.get(invite.guild.id, {}).pop(invite.code, None)

    async def _find_used_invite(self, guild: discord.Guild):
        """Best effort: επιστρέφει discord.Invite, το string 'VANITY', ή None."""
        before = _invite_cache.get(guild.id, {})
        try:
            current_invites = await guild.invites()
        except (discord.Forbidden, discord.HTTPException):
            current_invites = []
        current = {inv.code: inv for inv in current_invites}

        used = None
        for code, inv in current.items():
            if (inv.uses or 0) > before.get(code, 0):
                used = inv
                break

        vanity = None
        try:
            vanity = await guild.vanity_invite()
        except (discord.Forbidden, discord.HTTPException):
            vanity = None

        if used is None and vanity is not None and (vanity.uses or 0) > before.get("__vanity__", 0):
            used = "VANITY"

        if used is None:
            missing_codes = [c for c in before if c not in current and c != "__vanity__"]
            if len(missing_codes) == 1:
                try:
                    async for entry in guild.audit_logs(action=discord.AuditLogAction.invite_delete, limit=5):
                        if getattr(entry.target, "code", None) == missing_codes[0]:
                            used = entry.target
                            break
                except (discord.Forbidden, discord.HTTPException):
                    pass

        new_snapshot = {inv.code: inv.uses or 0 for inv in current_invites}
        if vanity is not None:
            new_snapshot["__vanity__"] = vanity.uses or 0
        _invite_cache[guild.id] = new_snapshot

        return used

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        guild = member.guild

        used = await self._find_used_invite(guild)
        inviter = None
        is_vanity = False
        if used == "VANITY":
            is_vanity = True
        elif used is not None and getattr(used, "inviter", None) is not None:
            inviter = used.inviter

        attribution = storage.get_store(ATTRIBUTION_STORE)
        stats = storage.get_store(STATS_STORE)
        entry = None

        if inviter is not None:
            inviter_key = str(inviter.id)
            attribution[str(member.id)] = inviter_key
            entry = _stats_entry(stats, inviter_key)
            entry["total"] += 1
            if member.id not in entry["joined_ids"]:
                entry["joined_ids"].append(member.id)
            storage.save(ATTRIBUTION_STORE, attribution)
            storage.save(STATS_STORE, stats)
        elif is_vanity:
            attribution[str(member.id)] = "vanity"
            storage.save(ATTRIBUTION_STORE, attribution)
        else:
            attribution[str(member.id)] = "unknown"
            storage.save(ATTRIBUTION_STORE, attribution)

        log_channel = guild.get_channel(config.INVITE_LOG_CHANNEL_ID)
        if not log_channel:
            return

        embed = discord.Embed(title="📨 Νέο μέλος μέσω Invite", color=config.EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.add_field(name="Μέλος", value=f"{member.mention} (`{member.id}`)", inline=False)
        if inviter is not None and entry is not None:
            embed.add_field(name="Προσκλήθηκε από", value=f"{inviter.mention} (`{inviter.id}`)", inline=False)
            embed.add_field(name="Σύνολο invites", value=str(entry["total"]), inline=True)
            embed.add_field(name="Ακόμα μέσα", value=str(len(entry["joined_ids"])), inline=True)
            embed.add_field(name="Έχουν φύγει", value=str(len(entry["left_ids"])), inline=True)
        elif is_vanity:
            embed.add_field(name="Προσκλήθηκε από", value="🔗 Vanity URL του server", inline=False)
        else:
            embed.add_field(name="Προσκλήθηκε από", value="Άγνωστο (δεν εντοπίστηκε invite)", inline=False)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        attribution = storage.get_store(ATTRIBUTION_STORE)
        inviter_key = attribution.get(str(member.id))

        if not inviter_key or inviter_key in ("unknown", "vanity"):
            return  # δεν ξέρουμε ποιος τον προσκάλεσε με συγκεκριμένο μέλος, τίποτα να ενημερώσουμε

        stats = storage.get_store(STATS_STORE)
        entry = _stats_entry(stats, inviter_key)
        if member.id in entry["joined_ids"]:
            entry["joined_ids"].remove(member.id)
        if member.id not in entry["left_ids"]:
            entry["left_ids"].append(member.id)
        storage.save(STATS_STORE, stats)

        log_channel = guild.get_channel(config.INVITE_LOG_CHANNEL_ID)
        if not log_channel:
            return

        inviter = guild.get_member(int(inviter_key)) if inviter_key.isdigit() else None
        embed = discord.Embed(title="📤 Μέλος έφυγε (είχε invite)", color=0xED4245, timestamp=discord.utils.utcnow())
        embed.add_field(name="Μέλος", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Είχε μπει από", value=(inviter.mention if inviter else f"`{inviter_key}`"), inline=False)
        embed.add_field(name="Σύνολο invites", value=str(entry["total"]), inline=True)
        embed.add_field(name="Ακόμα μέσα", value=str(len(entry["joined_ids"])), inline=True)
        embed.add_field(name="Έχουν φύγει", value=str(len(entry["left_ids"])), inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await log_channel.send(embed=embed)


    # ── /invites command ─────────────────────────────────────────────────────

    def _build_user_panel(self, guild: discord.Guild, member: discord.Member) -> ui.LayoutView:
        stats = storage.get_store(STATS_STORE)
        entry = stats.get(str(member.id), {"total": 0, "joined_ids": [], "left_ids": []})

        text = (
            f"## {emoji('invites','invites')} Invites — {member.mention}\n"
            f"{emoji('invites','invites')} **Σύνολο Invites:** {entry['total']}\n"
            f"{emoji('invites','joined')} **Ακόμα μέσα:** {len(entry['joined_ids'])}\n"
            f"{emoji('invites','left')} **Έχουν φύγει:** {len(entry['left_ids'])}"
        )

        container = ui.Container(accent_colour=discord.Colour.blurple())
        if member.display_avatar:
            section = ui.Section(accessory=ui.Thumbnail(media=member.display_avatar.url))
            section.add_item(ui.TextDisplay(text))
            container.add_item(section)
        else:
            container.add_item(ui.TextDisplay(text))

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view

    def _build_leaderboard_panel(self, guild: discord.Guild) -> ui.LayoutView:
        stats = storage.get_store(STATS_STORE)
        rows = sorted(stats.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)

        lines = [f"## {emoji('invites','leaderboard')} Invites Server — {guild.name}\n"]
        if not rows:
            lines.append("*Δεν υπάρχουν ακόμα καταγεγραμμένα invites.*")
        else:
            for i, (inviter_id, entry) in enumerate(rows[:25], start=1):
                lines.append(
                    f"`{i}.` <@{inviter_id}> — **{entry.get('total', 0)}** "
                    f"({emoji('invites','joined')} {len(entry.get('joined_ids', []))} · "
                    f"{emoji('invites','left')} {len(entry.get('left_ids', []))})"
                )

        container = ui.Container(accent_colour=discord.Colour.blurple())
        header_text = "\n".join(lines)
        if guild.icon:
            section = ui.Section(accessory=ui.Thumbnail(media=guild.icon.url))
            section.add_item(ui.TextDisplay(header_text))
            container.add_item(section)
        else:
            container.add_item(ui.TextDisplay(header_text))

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view

    @app_commands.command(name="invites", description="Δείχνει τα invites ενός μέλους, ή όλα τα invites του server")
    @app_commands.describe(user="Άφησέ το κενό για να δεις τα invites όλου του server")
    async def invites_cmd(self, interaction: discord.Interaction, user: discord.Member | None = None):
        if not member_has_any_role(interaction.user, config.STAFF_TEAM_ROLE_IDS):
            await interaction.response.send_message("⛔ Δεν έχεις δικαίωμα να χρησιμοποιήσεις αυτή την εντολή.", ephemeral=True)
            return

        if user is not None:
            view = self._build_user_panel(interaction.guild, user)
        else:
            view = self._build_leaderboard_panel(interaction.guild)

        await interaction.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracking(bot))
