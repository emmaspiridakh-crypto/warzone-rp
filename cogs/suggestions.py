"""
cogs/suggestions.py
---------------------
Requirement #4: Ο,τι γράψει κάποιος στο suggestions channel γίνεται αυτόματα
ένα "suggestion" message με upvote/downvote κουμπιά (Components V2),
μέτρηση ψήφων, και ping του συντάκτη.

ΣΗΜΕΙΩΣΗ: Αυτό είναι το ΜΟΝΟ panel που ΔΕΝ ενεργοποιείται με slash command —
ενεργοποιείται απλά όταν κάποιος γράψει στο config.SUGGESTIONS_CHANNEL_ID.
"""

from __future__ import annotations

import discord
from discord import ui
from discord.ext import commands

import config
from emojis import emoji
from utils import storage
from utils.components import build_base_container, add_separator, add_action_row, add_text

STORE_NAME = "suggestions"  # data/suggestions.json


class Suggestions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _build_view(self, *, author: discord.Member, text: str, upvotes: int, downvotes: int, msg_id: int) -> ui.LayoutView:
        container = build_base_container(
            title="💡 Νέο Suggestion",
            description=f"{author.mention}\n\n{text}",
            color=discord.Colour.gold(),
        )
        add_separator(container)
        add_text(container, f"**{emoji('suggestions', 'upvote')} {upvotes}**   ||   **{emoji('suggestions', 'downvote')} {downvotes}**")
        add_separator(container)
        up_btn = ui.Button(label="Upvote", style=discord.ButtonStyle.success,
                            emoji=emoji("suggestions", "upvote"), custom_id=f"suggestion_up:{msg_id}")
        down_btn = ui.Button(label="Downvote", style=discord.ButtonStyle.danger,
                              emoji=emoji("suggestions", "downvote"), custom_id=f"suggestion_down:{msg_id}")
        add_action_row(container, up_btn, down_btn)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        return view

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id != config.SUGGESTIONS_CHANNEL_ID:
            return

        content = message.content.strip()
        author = message.author

        try:
            await message.delete()
        except discord.Forbidden:
            pass

        # Στέλνουμε πρώτα placeholder για να πάρουμε ID, μετά edit με το σωστό custom_id
        temp_view = self._build_view(author=author, text=content, upvotes=0, downvotes=0, msg_id=0)
        sent = await message.channel.send(view=temp_view)

        store = storage.get_store(STORE_NAME)
        store[str(sent.id)] = {"author_id": author.id, "text": content, "upvotes": [], "downvotes": []}
        storage.save(STORE_NAME, store)

        real_view = self._build_view(author=author, text=content, upvotes=0, downvotes=0, msg_id=sent.id)
        await sent.edit(view=real_view)

    async def _handle_vote(self, interaction: discord.Interaction, msg_id: int, upvote: bool):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(msg_id))
        if not info:
            await interaction.response.send_message("Δεν βρέθηκε αυτό το suggestion.", ephemeral=True)
            return

        uid = interaction.user.id
        ups, downs = set(info["upvotes"]), set(info["downvotes"])

        if upvote:
            if uid in ups:
                ups.discard(uid)
            else:
                ups.add(uid)
                downs.discard(uid)
        else:
            if uid in downs:
                downs.discard(uid)
            else:
                downs.add(uid)
                ups.discard(uid)

        info["upvotes"], info["downvotes"] = list(ups), list(downs)
        store[str(msg_id)] = info
        storage.save(STORE_NAME, store)

        author = interaction.guild.get_member(info["author_id"])
        new_view = self._build_view(
            author=author or interaction.user, text=info["text"],
            upvotes=len(ups), downvotes=len(downs), msg_id=msg_id,
        )
        await interaction.response.edit_message(view=new_view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("suggestion_up:"):
            await self._handle_vote(interaction, int(custom_id.split(":")[1]), upvote=True)
        elif custom_id.startswith("suggestion_down:"):
            await self._handle_vote(interaction, int(custom_id.split(":")[1]), upvote=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
