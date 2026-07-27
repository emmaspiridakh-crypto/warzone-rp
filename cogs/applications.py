"""
cogs/applications.py
"""

from __future__ import annotations

import discord
from discord import ui, app_commands
from discord.ext import commands

import config
from emojis import emoji
from utils import storage
from utils.permissions import has_roles
from utils.components import build_base_container, add_separator, add_text, add_action_row, add_section_with_button

STORE_NAME = "applications"
LOCKS_STORE = "application_locks"


def _safe_name(text: str) -> str:
    text = text.lower().strip().replace(" ", "-")
    return "".join(c for c in text if c.isalnum() or c == "-")[:90]


def _is_locked(type_key: str) -> bool:
    locks = storage.get_store(LOCKS_STORE)
    return bool(locks.get(type_key, False))


APPLICATION_TYPE_CHOICES = [
    app_commands.Choice(name=data["label"], value=key)
    for key, data in config.APPLICATION_TYPES.items()
]


class DenyReasonModal(ui.Modal, title="Αιτιολογία Απόρριψης"):
    reason = ui.TextInput(label="Λόγος απόρριψης", style=discord.TextStyle.paragraph, required=True, max_length=500)

    def __init__(self, channel_id: int, cog: "Applications"):
        super().__init__()
        self.channel_id = channel_id
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.finalize_application(interaction, self.channel_id, accepted=False, reason=str(self.reason))


class Applications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------- PANEL ----------------
    @app_commands.command(name="panel-applications", description="Στέλνει το Applications panel")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID, config.MANAGER_ROLE_ID, config.STAFF_ROLE_ID)
    async def panel_applications(self, interaction: discord.Interaction):
        container = build_base_container(
            title="Warzone Reborn Roleplay - Applications",
            description="Επίλεξε σε τι θες να κάνεις αίτηση από το παρακάτω μενού.\n**Απαγορεύεται η χρήση AI.** Έχεις 30 λεπτά να ολοκληρώσεις αλλιώς θα απορριφθεί.",
            banner_url=config.APPLICATIONS_BANNER_URL,
        )
        add_separator(container)

        _app_info = {
            "elas":    {"description": "Γίνε μέλος της ΕΛ.ΑΣ — προστάτεψε πολίτες & διατήρησε την τάξη.",       "emoji_key": "elas"},
            "ekab":    {"description": "Γίνε διασώστης ΕΚΑΒ — βοήθα τραυματίες & χειρίσου έκτακτα περιστατικά.", "emoji_key": "ekab"},
            "fbi":     {"description": "Γίνε πράκτορας FBI — διερεύνησε σοβαρά εγκλήματα & απειλές.",            "emoji_key": "fbi"},
            "limeniko": {"description": "Γίνε μέλος του λιμενικού — προστάτεψε την πόλη",                        "emoji_key": "limeniko"},
            "staff":   {"description": "Γίνε μέλος του staff team — διαχειρίσου reports & τήρησε τους κανόνες.", "emoji_key": "staff"},
            "manager": {"description": "Θέση υψηλής ευθύνης — διαχειρίσου server & ομάδα staff.",               "emoji_key": "manager"},
        }

        options = []
        for key, data in config.APPLICATION_TYPES.items():
            info = _app_info.get(key, {"description": "", "emoji_key": "apply"})
            raw_emoji = emoji("applications", info["emoji_key"])
            options.append(
                discord.SelectOption(
                    label=data["label"],
                    value=key,
                    description=info["description"][:100],
                    emoji=raw_emoji if raw_emoji else None,
                )
            )

        select = ui.Select(
            placeholder="Επίλεξε τύπο αίτησης...",
            options=options,
            custom_id="app_select",
        )
        add_action_row(container, select)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await interaction.channel.send(view=view)
        await interaction.response.send_message("✅ Στάλθηκε.", ephemeral=True)

    # ---------------- APPLY -> δημιουργία channel ----------------
    async def start_apply(self, interaction: discord.Interaction, type_key: str):
        data = config.APPLICATION_TYPES.get(type_key)
        if not data:
            await interaction.response.send_message("Άγνωστος τύπος αίτησης.", ephemeral=True)
            return

        if _is_locked(type_key):
            await interaction.response.send_message(
                f"🔒 Οι αιτήσεις για **{data['label']}** είναι κλειδωμένες αυτή τη στιγμή. Δοκίμασε ξανά αργότερα.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        user = interaction.user

        store = storage.get_store(STORE_NAME)
        for ch_id, info in store.items():
            if info.get("user_id") == user.id and info.get("status") not in ("closed", "denied", "accepted"):
                channel = guild.get_channel(int(ch_id))
                if channel:
                    await interaction.response.send_message(f"Έχεις ήδη ανοιχτή αίτηση: {channel.mention}", ephemeral=True)
                    return

        category = guild.get_channel(config.APPLICATIONS_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_id in config.STAFF_TEAM_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"application-{type_key}-{_safe_name(user.display_name)}", category=category, overwrites=overwrites
        )

        store[str(channel.id)] = {
            "type": type_key, "user_id": user.id, "status": "pending",
            "current_step": 0, "answers": [],
        }
        storage.save(STORE_NAME, store)

        container = build_base_container(
            title=f"{data['label']} Application",
            description=f"{user.mention}\nΠάτησε **Start Your Application** όταν είσαι έτοιμος/η. Χρόνος ολοκλήρωσης: 30 λεπτά",
        )
        add_separator(container)
        start_btn = ui.Button(label="Start Your Application", style=discord.ButtonStyle.success, custom_id=f"app_start:{channel.id}")
        close_btn = ui.Button(label="Close", style=discord.ButtonStyle.danger, custom_id=f"app_close:{channel.id}")
        ping_btn = ui.Button(label="Ping User", style=discord.ButtonStyle.secondary,
                              emoji=emoji("tickets", "ping"), custom_id=f"app_ping_user:{channel.id}")
        add_action_row(container, start_btn, close_btn, ping_btn)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await channel.send(view=view)
        await interaction.response.send_message(f"✅ Η αίτηση σου: {channel.mention}", ephemeral=True)

    # ---------------- START -> πρώτη ερώτηση ----------------
    async def send_question(self, channel: discord.TextChannel, type_key: str, step: int):
        questions = config.APPLICATION_TYPES[type_key]["questions"]
        container = build_base_container(
            title=f"Ερώτηση {step + 1}/{len(questions)}",
            description=questions[step] + "\n\n*Γράψε την απάντηση σου στο channel.*",
        )
        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await channel.send(view=view)

    async def handle_start(self, interaction: discord.Interaction, channel_id: int):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(channel_id))
        if not info or interaction.user.id != info["user_id"]:
            await interaction.response.send_message("Μόνο αυτός που έκανε την αίτηση μπορεί να την ξεκινήσει.", ephemeral=True)
            return
        info["status"] = "answering"
        store[str(channel_id)] = info
        storage.save(STORE_NAME, store)
        await interaction.response.send_message("📝 Ξεκινάμε.", ephemeral=True)
        await self.send_question(interaction.channel, info["type"], 0)

    # ---------------- on_message -> καταγραφή απαντήσεων ----------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        store = storage.get_store(STORE_NAME)
        info = store.get(str(message.channel.id))
        if not info or info.get("status") != "answering" or message.author.id != info["user_id"]:
            return

        questions = config.APPLICATION_TYPES[info["type"]]["questions"]
        info["answers"].append(message.content)
        step = info["current_step"] + 1
        info["current_step"] = step

        if step < len(questions):
            store[str(message.channel.id)] = info
            storage.save(STORE_NAME, store)
            await self.send_question(message.channel, info["type"], step)
        else:
            info["status"] = "ready_to_submit"
            store[str(message.channel.id)] = info
            storage.save(STORE_NAME, store)

            container = build_base_container(
                title="✅ Ολοκλήρωσες τις ερωτήσεις!",
                description="Πάτησε **Send** για να στείλεις την αίτηση.",
            )
            send_btn = ui.Button(label="Send", style=discord.ButtonStyle.success,
                                  emoji=emoji("applications", "send"), custom_id=f"app_send:{message.channel.id}")
            add_action_row(container, send_btn)
            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            await message.channel.send(view=view)

    # ---------------- SEND -> log channel με Accept/Deny ----------------
    async def handle_send(self, interaction: discord.Interaction, channel_id: int):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(channel_id))
        if not info or interaction.user.id != info["user_id"]:
            await interaction.response.send_message("Μόνο αυτός που έκανε την αίτηση μπορεί να τη στείλει.", ephemeral=True)
            return

        guild = interaction.guild
        applicant = guild.get_member(info["user_id"])
        log_channel = guild.get_channel(config.LOG_APPLICATIONS_CHANNEL_ID)

        type_label = config.APPLICATION_TYPES[info["type"]]["label"]
        questions = config.APPLICATION_TYPES[info["type"]]["questions"]

        container = build_base_container(
            title=f"📋 Νέα Αίτηση — {type_label}",
            description=f"User: {applicant.mention if applicant else info['user_id']}",
        )
        add_separator(container)
        for q, a in zip(questions, info["answers"]):
            add_text(container, f"**{q}**\n{a}")
        add_separator(container)
        accept_btn = ui.Button(label="Accept", style=discord.ButtonStyle.success,
                                emoji=emoji("applications", "accept"), custom_id=f"app_accept:{channel_id}")
        deny_btn = ui.Button(label="Deny", style=discord.ButtonStyle.danger,
                              emoji=emoji("applications", "deny"), custom_id=f"app_deny:{channel_id}")
        add_action_row(container, accept_btn, deny_btn)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        log_message = await log_channel.send(view=view)

        info["status"] = "submitted"
        info["log_message_id"] = log_message.id
        store[str(channel_id)] = info
        storage.save(STORE_NAME, store)

        await interaction.response.send_message(
            "✅ Η αίτηση στάλθηκε! Θα ενημερωθείς με DΜ, φρόντισε να μην τα έχεις κλειστά.", ephemeral=False
        )

    # ---------------- ACCEPT / DENY ----------------
    async def finalize_application(self, interaction: discord.Interaction, channel_id: int, *, accepted: bool, reason: str | None = None):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(channel_id))
        if not info:
            await interaction.response.send_message("Δεν βρέθηκε η αίτηση.", ephemeral=True)
            return

        guild = interaction.guild
        applicant = guild.get_member(info["user_id"])

        if accepted:
            role_id = config.APPLICATION_ACCEPTED_ROLES.get(info["type"])
            if role_id:
                role = guild.get_role(role_id)
                if role and applicant:
                    await applicant.add_roles(role, reason="Application accepted")
            info["status"] = "accepted"
            if info["type"] in ("staff", "manager"):
                dm_text = (
                    f"✅ Η αίτηση σου ({config.APPLICATION_TYPES[info['type']]['label']}) έγινε **δεκτή**! "
                    f"Ενημέρωσε στο αντίστοιχο channel πότε μπορείς για το interview σου."
                )
            else:
                dm_text = f"✅ Η αίτηση σου ({config.APPLICATION_TYPES[info['type']]['label']}) έγινε **δεκτή**!"
        else:
            info["status"] = "denied"
            dm_text = f"❌ Η αίτηση σου ({config.APPLICATION_TYPES[info['type']]['label']}) **απορρίφθηκε**.\nΛόγος: {reason}"

        info["decided_by"] = interaction.user.id
        info["decision_reason"] = reason
        store[str(channel_id)] = info
        storage.save(STORE_NAME, store)

        if applicant:
            try:
                await applicant.send(dm_text)
            except discord.Forbidden:
                pass

        type_label = config.APPLICATION_TYPES[info["type"]]["label"]
        questions = config.APPLICATION_TYPES[info["type"]]["questions"]
        status_text = (
            f"✅ **Accepted**\nΑπό: {interaction.user.mention}"
            if accepted
            else f"❌ **Denied**\nΑπό: {interaction.user.mention}\nΛόγος: {reason}"
        )

        container = build_base_container(
            title=f"Αίτηση — {type_label}",
            description=f"User: {applicant.mention if applicant else info['user_id']}",
        )
        add_separator(container)
        for q, a in zip(questions, info["answers"]):
            add_text(container, f"**{q}**\n{a}")
        add_separator(container)
        add_text(container, status_text)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)

        if interaction.response.is_done():
            await interaction.message.edit(view=view)
        else:
            await interaction.response.edit_message(view=view)

    # ---------------- CLOSE / PING ----------------
    async def handle_close(self, interaction: discord.Interaction, channel_id: int):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(channel_id))
        if info:
            info["status"] = "closed"
            store[str(channel_id)] = info
            storage.save(STORE_NAME, store)
        await interaction.response.send_message("🔒 Το channel κλείνει...", ephemeral=False)
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            await channel.delete(reason=f"Application closed by {interaction.user}")

    async def handle_ping_user(self, interaction: discord.Interaction, channel_id: int):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(channel_id))
        if not info:
            await interaction.response.send_message("Δεν βρέθηκε η αίτηση.", ephemeral=True)
            return

        if not has_roles(interaction.user, config.STAFF_TEAM_ROLE_IDS):
            await interaction.response.send_message("⛔ Μόνο το staff team μπορεί να κάνει ping τον χρήστη.", ephemeral=True)
            return

        guild = interaction.guild
        applicant = guild.get_member(info["user_id"])
        await interaction.response.send_message(f"🔔 {applicant.mention if applicant else ''}", ephemeral=False)
        if applicant:
            try:
                await applicant.send(f"🔔 Έχεις ειδοποίηση στην αίτηση σου: {interaction.channel.mention}")
            except discord.Forbidden:
                pass

    # ---------------- LOCK / UNLOCK ----------------
    @app_commands.command(name="lockapplication", description="Κλειδώνει έναν τύπο αίτησης")
    @app_commands.describe(name="Ο τύπος αίτησης προς κλείδωμα")
    @app_commands.choices(name=APPLICATION_TYPE_CHOICES)
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID)
    async def lockapplication(self, interaction: discord.Interaction, name: app_commands.Choice[str]):
        locks = storage.get_store(LOCKS_STORE)
        locks[name.value] = True
        storage.save(LOCKS_STORE, locks)
        await interaction.response.send_message(f"🔒 Οι αιτήσεις **{name.name}** κλειδώθηκαν.", ephemeral=True)

    @app_commands.command(name="unlockapplication", description="Ξεκλειδώνει έναν τύπο αίτησης")
    @app_commands.describe(name="Ο τύπος αίτησης προς ξεκλείδωμα")
    @app_commands.choices(name=APPLICATION_TYPE_CHOICES)
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID)
    async def unlockapplication(self, interaction: discord.Interaction, name: app_commands.Choice[str]):
        locks = storage.get_store(LOCKS_STORE)
        locks[name.value] = False
        storage.save(LOCKS_STORE, locks)
        await interaction.response.send_message(f"🔓 Οι αιτήσεις **{name.name}** ξεκλειδώθηκαν.", ephemeral=True)

    @app_commands.command(name="lockallapplications", description="Κλειδώνει ΟΛΟΥΣ τους τύπους αιτήσεων μαζί")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID)
    async def lockallapplications(self, interaction: discord.Interaction):
        locks = {key: True for key in config.APPLICATION_TYPES}
        storage.save(LOCKS_STORE, locks)
        await interaction.response.send_message("🔒 Όλες οι αιτήσεις κλειδώθηκαν.", ephemeral=True)

    @app_commands.command(name="unlockallapplications", description="Ξεκλειδώνει ΟΛΟΥΣ τους τύπους αιτήσεων μαζί")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID)
    async def unlockallapplications(self, interaction: discord.Interaction):
        locks = {key: False for key in config.APPLICATION_TYPES}
        storage.save(LOCKS_STORE, locks)
        await interaction.response.send_message("🔓 Όλες οι αιτήσεις ξεκλειδώθηκαν.", ephemeral=True)

    # ---------------- Κεντρικός listener ----------------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id", "")

        if custom_id == "app_select":
            value = interaction.data["values"][0]
            await self.start_apply(interaction, value)
        elif custom_id.startswith("app_start:"):
            await self.handle_start(interaction, int(custom_id.split(":")[1]))
        elif custom_id.startswith("app_send:"):
            await self.handle_send(interaction, int(custom_id.split(":")[1]))
        elif custom_id.startswith("app_close:"):
            await self.handle_close(interaction, int(custom_id.split(":")[1]))
        elif custom_id.startswith("app_ping_user:"):
            await self.handle_ping_user(interaction, int(custom_id.split(":")[1]))
        elif custom_id.startswith("app_accept:"):
            channel_id = int(custom_id.split(":")[1])
            if not has_roles(interaction.user, config.STAFF_TEAM_ROLE_IDS):
                await interaction.response.send_message("⛔ Δεν έχεις δικαίωμα.", ephemeral=True)
                return
            await self.finalize_application(interaction, channel_id, accepted=True)
        elif custom_id.startswith("app_deny:"):
            channel_id = int(custom_id.split(":")[1])
            if not has_roles(interaction.user, config.STAFF_TEAM_ROLE_IDS):
                await interaction.response.send_message("⛔ Δεν έχεις δικαίωμα.", ephemeral=True)
                return
            await interaction.response.send_modal(DenyReasonModal(channel_id, self))


async def setup(bot: commands.Bot):
    await bot.add_cog(Applications(bot))
