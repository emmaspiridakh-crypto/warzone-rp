"""
cogs/bot_status.py
---------------------
Επιτρέπει στο Ownership να αλλάζει το status του bot κάτω από το όνομά του
(π.χ. "Watching Server") με ένα slash command — χωρίς να πειράξει κώδικα.
Το status αποθηκεύεται (μέσω utils.storage -> Turso) και ξαναμπαίνει
αυτόματα κάθε φορά που το bot ξεκινάει/κάνει redeploy.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage
from utils.permissions import member_has_any_role
import config

STORE = "bot_status"

ACTIVITY_TYPES = {
    "playing": discord.ActivityType.playing,
    "watching": discord.ActivityType.watching,
    "listening": discord.ActivityType.listening,
    "competing": discord.ActivityType.competing,
}


class BotStatus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _apply_saved_status(self):
        data = storage.get_store(STORE)
        activity_type = data.get("type", "watching")
        text = data.get("text", "τον server")
        activity = discord.Activity(type=ACTIVITY_TYPES.get(activity_type, discord.ActivityType.watching), name=text)
        try:
            await self.bot.change_presence(activity=activity)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        await self._apply_saved_status()

    @app_commands.command(name="setstatus", description="Αλλάζει το status του bot (μόνο Ownership)")
    @app_commands.describe(type="Τύπος status", text="Το κείμενο που θα εμφανίζεται")
    @app_commands.choices(type=[
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Watching", value="watching"),
        app_commands.Choice(name="Listening", value="listening"),
        app_commands.Choice(name="Competing", value="competing"),
    ])
    async def setstatus(self, interaction: discord.Interaction, type: app_commands.Choice[str], text: str):
        if not member_has_any_role(interaction.user, [config.OWNERSHIP_ROLE_ID]):
            await interaction.response.send_message("⛔ Μόνο το Ownership μπορεί να αλλάξει το status του bot.", ephemeral=True)
            return

        storage.save(STORE, {"type": type.value, "text": text})
        await self._apply_saved_status()

        await interaction.response.send_message(
            f"✅ Το status ενημερώθηκε: **{type.name} {text}**", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BotStatus(bot))
