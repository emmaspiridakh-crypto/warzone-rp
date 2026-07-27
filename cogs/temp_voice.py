"""
cogs/temp_voice.py
---------------------
Requirement #6: Όποιος μπει στο "Join to Create" channel, παίρνει το δικό του
temp voice channel. Διαγράφεται μόλις αδειάσει. Ping στο staff channel (ίδιο
μηχανισμό με τα tickets) όταν δημιουργείται ΚΑΙ όταν κλείνει/αδειάζει
ένα temp channel.
"""

from __future__ import annotations

import discord
from discord.ext import commands

import config
from emojis import emoji

# channel_id -> owner_id (in-memory· αν restart το bot ενώ υπάρχουν ανοιχτά temp
# channels, θα παραμείνουν "ορφανά" μέχρι να αδειάσουν - δεν είναι πρόβλημα γιατί
# έτσι κι αλλιώς αδειάζουν μόνα τους).
active_temp_channels: dict[int, int] = {}


class TempVoice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild

        # --- Join to Create ---
        if after.channel and after.channel.id == config.TEMP_VOICE_JOIN_CHANNEL_ID:
            category = guild.get_channel(config.TEMP_VOICE_CATEGORY_ID)
            new_channel = await guild.create_voice_channel(
                name=f"🔊 {member.display_name}", category=category,
            )
            await new_channel.set_permissions(member, manage_channels=True, connect=True, speak=True)
            await member.move_to(new_channel)
            active_temp_channels[new_channel.id] = member.id

            ping_channel = guild.get_channel(config.STAFF_PING_CHANNEL_ID)
            if ping_channel:
                await ping_channel.send(
                    f"{emoji('voice', 'temp')} Νέο temp voice channel από {member.mention}"
                )

        # --- Διαγραφή temp channel όταν αδειάσει ---
        if before.channel and before.channel.id in active_temp_channels:
            if len(before.channel.members) == 0:
                channel_id = before.channel.id
                owner_id = active_temp_channels.get(channel_id)
                try:
                    await before.channel.delete(reason="Temp voice channel άδειο")
                except discord.NotFound:
                    pass
                active_temp_channels.pop(channel_id, None)

                ping_channel = guild.get_channel(config.STAFF_PING_CHANNEL_ID)
                if ping_channel:
                    owner = guild.get_member(owner_id) if owner_id else None
                    owner_text = owner.mention if owner else (f"<@{owner_id}>" if owner_id else "Άγνωστο μέλος")
                    await ping_channel.send(
                        f"{emoji('voice', 'leave')} Το temp voice channel του {owner_text} έκλεισε."
                    )


async def setup(bot: commands.Bot):
    await bot.add_cog(TempVoice(bot))
