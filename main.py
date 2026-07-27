"""
main.py
--------
Entry point του bot. Τρέχει το fake Flask server (keep_alive) και μετά
ξεκινάει το discord bot, φορτώνοντας όλα τα cogs.
"""

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
from keep_alive import keep_alive

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

intents = discord.Intents.default()
intents.members = True          # ΑΠΑΡΑΙΤΗΤΟ: join/leave logs, role logs, server status
intents.message_content = True  # ΑΠΑΡΑΙΤΗΤΟ: ! commands, suggestions, application answers
intents.presences = True        # ΑΠΑΡΑΙΤΗΤΟ: online members count
intents.voice_states = True     # ΑΠΑΡΑΙΤΗΤΟ: temp voice, staff activity, voice logs

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents, help_command=None)

COGS = [
    "cogs.tickets",
    "cogs.suggestions",
    "cogs.moderation",
    "cogs.temp_voice",
    "cogs.staff_activity",
    "cogs.logging_events",
    "cogs.applications",
    "cogs.server_status",
    "cogs.panel_command",
    "cogs.autorole",
    "cogs.invite_tracking",
    "cogs.giveaways",
    "cogs.warnings",
]


@bot.event
async def on_ready():
    log.info(f"✅ Συνδέθηκε ως {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        log.info(f"🔄 Sync {len(synced)} slash commands.")
    except Exception as e:
        log.error(f"Σφάλμα στο sync: {e}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.error(f"Slash command error [{interaction.command and interaction.command.name}]: {error}", exc_info=error)
    msg = f"❌ Σφάλμα: `{error}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        log.error(f"Αποτυχία αποστολής error message: {e}")


async def main():
    keep_alive()  # ξεκινάει το fake Flask server για UptimeRobot
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                log.info(f"✅ Φορτώθηκε: {cog}")
            except Exception as e:
                log.error(f"❌ Αποτυχία φόρτωσης {cog}: {e}")
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    if not config.TOKEN:
        raise RuntimeError("⚠️ Δεν βρέθηκε DISCORD_TOKEN. Βάλε το στο .env (local) ή Environment Variables (Render).")
    asyncio.run(main())
