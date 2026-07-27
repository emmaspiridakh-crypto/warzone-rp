"""
utils/permissions.py
---------------------
Κεντρικά role-checks. Όλα τα cogs τα χρησιμοποιούν ώστε να μην ξαναγράφουμε
τον ίδιο έλεγχο παντού.
"""

import discord
from discord import app_commands
from discord.ext import commands

import config


def member_has_any_role(member: discord.Member, role_ids: list[int]) -> bool:
    member_role_ids = {r.id for r in member.roles}
    return any(rid in member_role_ids for rid in role_ids)


# ---------- Prefix command checks (commands.check) ----------

def is_staff_team():
    """Staff, Manager, Ownership"""
    async def predicate(ctx: commands.Context) -> bool:
        return member_has_any_role(ctx.author, config.STAFF_TEAM_ROLE_IDS)
    return commands.check(predicate)


def is_ownership_only():
    async def predicate(ctx: commands.Context) -> bool:
        return member_has_any_role(ctx.author, [config.OWNERSHIP_ROLE_ID])
    return commands.check(predicate)


def is_founder_only():
    async def predicate(ctx: commands.Context) -> bool:
        return member_has_any_role(ctx.author, [config.FOUNDER_ROLE_ID])
    return commands.check(predicate)


# ---------- Slash command checks (app_commands.check) ----------

def slash_is_staff_team():
    async def predicate(interaction: discord.Interaction) -> bool:
        return member_has_any_role(interaction.user, config.STAFF_TEAM_ROLE_IDS)
    return app_commands.check(predicate)


def slash_is_ownership_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        return member_has_any_role(interaction.user, [config.OWNERSHIP_ROLE_ID])
    return app_commands.check(predicate)


# ---------- Γενικά helpers (χρήσιμα μέσα σε button callbacks) ----------

def has_roles(member: discord.Member, role_ids: list[int]) -> bool:
    return member_has_any_role(member, role_ids)
