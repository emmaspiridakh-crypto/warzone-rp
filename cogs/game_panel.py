"""
cogs/game_panel.py
---------------------
/panel-game -> Components V2 panel: banner, separator, live status, separator,
"Connect" κουμπί που πάει στη σελίδα του Roblox game (universe id στο config.py).

Ζωντανό player count μέσω του δημόσιου Roblox games API (games.roblox.com).
Αν το API δεν απαντήσει, δείχνει "—" αντί να σκάσει.
"""

from __future__ import annotations

import aiohttp
import discord
from discord import app_commands, ui
from discord.ext import commands

import config
from emojis import emoji
from utils.permissions import slash_is_staff_team


async def _fetch_game_info(universe_id: int) -> dict:
    url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status != 200:
                    return {}
                data = await resp.json()
                games = data.get("data") or []
                return games[0] if games else {}
    except Exception:
        return {}


class GamePanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def build_panel(self, guild: discord.Guild) -> ui.LayoutView:
        info = await _fetch_game_info(config.ROBLOX_UNIVERSE_ID)
        playing = info.get("playing")
        visits = info.get("visits")
        name = info.get("name") or "Warzone RP"

        status_text = (
            f"## {emoji('game','status')} {name}\n"
            f"{emoji('game','status')} **Παίκτες τώρα:** {playing if playing is not None else '—'}\n"
            f"{emoji('invites','invites')} **Συνολικές επισκέψεις:** {visits if visits is not None else '—'}"
        )

        container = ui.Container(accent_colour=discord.Colour.gold())

        if config.GAME_PANEL_BANNER_URL:
            container.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=config.GAME_PANEL_BANNER_URL)))
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        container.add_item(ui.TextDisplay(status_text))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        connect_btn = ui.Button(
            label="Connect",
            style=discord.ButtonStyle.link,
            emoji=emoji("game", "connect") or "🔗",
            url=config.ROBLOX_GAME_URL,
        )
        row = ui.ActionRow()
        row.add_item(connect_btn)
        container.add_item(row)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view

    @app_commands.command(name="panel-game", description="Στέλνει το panel σύνδεσης με το Roblox game")
    @slash_is_staff_team()
    async def panel_game(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        view = await self.build_panel(interaction.guild)
        await interaction.channel.send(view=view)
        await interaction.followup.send("✅ Το game panel στάλθηκε.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamePanel(bot))
