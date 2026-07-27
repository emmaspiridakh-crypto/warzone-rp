"""
cogs/server_status.py
------------------------
Live stats σε voice channels.
Χρησιμοποιεί debounce (1 δευτερόλεπτο) ώστε πολλαπλά γρήγορα events
να συγχωνεύονται σε ένα μόνο API call — αμεσότητα χωρίς rate limit spam.
Backup loop κάθε 5 λεπτά για ασφάλεια.

ΑΠΑΡΑΙΤΗΤΟ στο main.py:
    intents.members   = True
    intents.presences = True
"""

from __future__ import annotations

import asyncio
import discord
from discord.ext import commands, tasks

import config
from emojis import emoji

_last_values: dict[str, str] = {}


def _counts(guild: discord.Guild):
    members = sum(1 for m in guild.members if not m.bot)
    online  = sum(1 for m in guild.members if not m.bot and m.status != discord.Status.offline)
    bots    = sum(1 for m in guild.members if m.bot)
    boosts  = guild.premium_subscription_count or 0
    return members, online, boosts, bots


class ServerStatus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending: dict[int, asyncio.Task] = {}  # guild_id -> debounce task

    # ── Core update ──────────────────────────────────────────────────────────

    async def update_stats(self, guild: discord.Guild):
        members, online, boosts, bots = _counts(guild)

        targets = {
            "members": (config.STATUS_MEMBERS_CHANNEL_ID, f"{emoji('status','members')} Members: {members}"),
            "online":  (config.STATUS_ONLINE_CHANNEL_ID,  f"{emoji('status','online')} Online: {online}"),
            "boosts":  (config.STATUS_BOOSTS_CHANNEL_ID,  f"{emoji('status','boost')} Boosts: {boosts}"),
            "bots":    (config.STATUS_BOTS_CHANNEL_ID,    f"{emoji('status','bots')} Bots: {bots}"),
        }

        for key, (channel_id, new_name) in targets.items():
            cache_key = f"{guild.id}:{key}"
            if _last_values.get(cache_key) == new_name:
                continue  # δεν άλλαξε τίποτα, skip
            channel = guild.get_channel(channel_id)
            if channel:
                try:
                    await channel.edit(name=new_name)
                    _last_values[cache_key] = new_name
                except discord.HTTPException:
                    pass  # rate limit του Discord — θα ξαναπροσπαθήσει στο επόμενο trigger

    # ── Debounce ─────────────────────────────────────────────────────────────

    def _schedule_update(self, guild: discord.Guild):
        """
        Ακυρώνει τυχόν εκκρεμή update για αυτό το guild και φτιάχνει νέο
        με 1 δευτερόλεπτο καθυστέρηση. Έτσι αν έρθουν 10 events μαζί,
        γίνεται μόνο 1 API call.
        """
        existing = self._pending.get(guild.id)
        if existing and not existing.done():
            existing.cancel()

        async def _delayed():
            await asyncio.sleep(1)
            await self.update_stats(guild)
            self._pending.pop(guild.id, None)

        self._pending[guild.id] = asyncio.create_task(_delayed())

    # ── Backup loop (κάθε 5 λεπτά) ──────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def _refresh_loop(self):
        for guild in self.bot.guilds:
            await self.update_stats(guild)

    @_refresh_loop.before_loop
    async def _before_refresh(self):
        await self.bot.wait_until_ready()

    # ── Events ────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        self._refresh_loop.start()
        for guild in self.bot.guilds:
            await self.update_stats(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        self._schedule_update(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self._schedule_update(member.guild)

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if before.status != after.status:
            self._schedule_update(after.guild)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        if before.premium_subscription_count != after.premium_subscription_count:
            self._schedule_update(after)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Πιάνει αλλαγές bot status (π.χ. νέο bot προστέθηκε/αφαιρέθηκε)
        if before.bot != after.bot:
            self._schedule_update(after.guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerStatus(bot))
