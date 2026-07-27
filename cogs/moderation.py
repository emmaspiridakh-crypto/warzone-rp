"""
cogs/moderation.py
---------------------
Requirement #5. Όλες οι εντολές με πρόθεμα "!" (commands.Bot prefix).

Permissions:
    ban/unban/kick/timeout/untimeout/clearmessages -> Staff, Manager, Ownership
    say / say2                                      -> Ownership only
    dmall                                           -> Founder only

Κάθε εντολή logάρει σε ΔΙΚΟ ΤΗΣ channel, εκτός say/say2/dmall που μοιράζονται ένα.
Τα logs λένε πάντα: ποιος έκανε την ενέργεια, σε ποιον, τι, και πότε.
"""

from __future__ import annotations

import re
import datetime

import discord
from discord.ext import commands

import config
from utils.permissions import is_staff_team, is_ownership_only, is_founder_only


def _log_embed(guild: discord.Guild, *, title: str, moderator: discord.Member, target: str, reason: str | None) -> discord.Embed:
    embed = discord.Embed(title=title, color=config.EMBED_COLOR, timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="Moderator", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
    embed.add_field(name="Target", value=target, inline=False)
    embed.add_field(name="Reason", value=reason or "—", inline=False)
    embed.add_field(name="Ώρα", value=discord.utils.format_dt(datetime.datetime.now(datetime.timezone.utc), style="F"), inline=False)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


async def _send_log(guild: discord.Guild, channel_id: int, embed: discord.Embed):
    channel = guild.get_channel(channel_id)
    if channel:
        await channel.send(embed=embed)


def _parse_duration(text: str) -> datetime.timedelta | None:
    """Δέχεται π.χ. 10m, 1h, 2d, 30s"""
    match = re.fullmatch(r"(\d+)([smhd])", text.strip().lower())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    return {
        "s": datetime.timedelta(seconds=amount),
        "m": datetime.timedelta(minutes=amount),
        "h": datetime.timedelta(hours=amount),
        "d": datetime.timedelta(days=amount),
    }[unit]


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- BAN ----------------
    @commands.command(name="ban")
    @is_staff_team()
    async def ban_cmd(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        await member.ban(reason=reason)
        await ctx.send(f"🔨 Ο {member.mention} έκανε ban.")
        await _send_log(ctx.guild, config.LOG_BAN_CHANNEL_ID,
                         _log_embed(ctx.guild, title="🔨 Ban", moderator=ctx.author,
                                    target=f"{member.mention} (`{member.id}`)", reason=reason))

    # ---------------- UNBAN ----------------
    @commands.command(name="unban")
    @is_staff_team()
    async def unban_cmd(self, ctx: commands.Context, user_id: int, *, reason: str = None):
        user = await self.bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f"✅ Ο {user.mention} έκανε unban.")
        await _send_log(ctx.guild, config.LOG_UNBAN_CHANNEL_ID,
                         _log_embed(ctx.guild, title="✅ Unban", moderator=ctx.author,
                                    target=f"{user.mention} (`{user.id}`)", reason=reason))

    # ---------------- KICK ----------------
    @commands.command(name="kick")
    @is_staff_team()
    async def kick_cmd(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        await member.kick(reason=reason)
        await ctx.send(f"👋 Ο {member.mention} έκανε kick.")
        await _send_log(ctx.guild, config.LOG_KICK_CHANNEL_ID,
                         _log_embed(ctx.guild, title="👋 Kick", moderator=ctx.author,
                                    target=f"{member.mention} (`{member.id}`)", reason=reason))

    # ---------------- TIMEOUT ----------------
    @commands.command(name="timeout")
    @is_staff_team()
    async def timeout_cmd(self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = None):
        delta = _parse_duration(duration)
        if delta is None:
            await ctx.send("⚠️ Λάθος χρόνος βλάκα. Κάνε: 10s / 10m / 1h / 1d")
            return
        await member.timeout(delta, reason=reason)
        await ctx.send(f"⏱️ Ο {member.mention} πήρε timeout για {duration}.")
        await _send_log(ctx.guild, config.LOG_TIMEOUT_CHANNEL_ID,
                         _log_embed(ctx.guild, title="⏱️ Timeout", moderator=ctx.author,
                                    target=f"{member.mention} (`{member.id}`) — {duration}", reason=reason))

    # ---------------- UNTIMEOUT ----------------
    @commands.command(name="untimeout")
    @is_staff_team()
    async def untimeout_cmd(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        await member.timeout(None, reason=reason)
        await ctx.send(f"✅ Αφαιρέθηκε το timeout από {member.mention}.")
        await _send_log(ctx.guild, config.LOG_UNTIMEOUT_CHANNEL_ID,
                         _log_embed(ctx.guild, title="✅ Untimeout", moderator=ctx.author,
                                    target=f"{member.mention} (`{member.id}`)", reason=reason))

    # ---------------- CLEAR MESSAGES ----------------
    @commands.command(name="clearmessages")
    @is_staff_team()
    async def clear_cmd(self, ctx: commands.Context, amount: int):
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 για να σβήσει και το ίδιο το !clearmessages
        await ctx.send(f"🧹 Σβήστηκαν {len(deleted) - 1} μηνύματα.", delete_after=5)
        await _send_log(ctx.guild, config.LOG_CLEARMESSAGES_CHANNEL_ID,
                         _log_embed(ctx.guild, title="🧹 Clear Messages", moderator=ctx.author,
                                    target=f"#{ctx.channel.name}", reason=f"{len(deleted) - 1} μηνύματα"))

    # ---------------- SAY ----------------
    @commands.command(name="say")
    @is_ownership_only()
    async def say_cmd(self, ctx: commands.Context, *, text: str):
        await ctx.message.delete()
        await ctx.send(text)
        await _send_log(ctx.guild, config.LOG_SAY_DMALL_CHANNEL_ID,
                         _log_embed(ctx.guild, title="📢 Say", moderator=ctx.author,
                                    target=f"#{ctx.channel.name}", reason=text))

    # ---------------- SAY2 (embed + thumbnail) ----------------
    @commands.command(name="say2")
    @is_ownership_only()
    async def say2_cmd(self, ctx: commands.Context, *, text: str):
        await ctx.message.delete()
        embed = discord.Embed(description=text, color=config.EMBED_COLOR)
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)
        await _send_log(ctx.guild, config.LOG_SAY_DMALL_CHANNEL_ID,
                         _log_embed(ctx.guild, title="📢 Say2", moderator=ctx.author,
                                    target=f"#{ctx.channel.name}", reason=text))

    # ---------------- DM ALL ----------------
    @commands.command(name="dmall")
    @is_founder_only()
    async def dmall_cmd(self, ctx: commands.Context, *, text: str):
        sent, failed = 0, 0
        status_msg = await ctx.send("📨 Στέλνετε βλάκα περίμενε")
        for member in ctx.guild.members:
            if member.bot:
                continue
            try:
                await member.send(text)
                sent += 1
            except discord.Forbidden:
                failed += 1
            await __import__("asyncio").sleep(1)  # αποφυγή rate limit
        await status_msg.edit(content=f"✅ Στάλθηκε σε {sent} μέλη. Αποτυχία σε {failed}.")
        await _send_log(ctx.guild, config.LOG_SAY_DMALL_CHANNEL_ID,
                         _log_embed(ctx.guild, title="📨 DM All", moderator=ctx.author,
                                    target=f"{sent} sent / {failed} failed", reason=text))

    # ---------------- Error handling για permission checks ----------------
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("⛔ Δεν έχεις δικαίωμα να χρησιμοποιήσεις την εντολή.", delete_after=5)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("⚠️ Δεν βρέθηκε ο μπρατ.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Λείπει το id ή το username: `{error.param.name}`", delete_after=5)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
