"""
cogs/tickets.py
-----------------
Καλύπτει τις απαιτήσεις #1, #2, #3 (όλα είναι το ίδιο "ticket system" κάτω
από το καπό, απλά διαφέρει το panel/visibility/category).

Persistence pattern για τα buttons/select:
    Δεν χρησιμοποιούμε discord.py callbacks πάνω στα ίδια τα Button/Select
    αντικείμενα (γιατί αυτά "χάνονται" μετά από restart του bot, εκτός αν
    κάνεις πολύπλοκο dynamic-items setup). Αντί αυτού:
      1. Στέλνουμε τα components με ΣΤΑΘΕΡΑ custom_id (π.χ. "ticket_close:<channel_id>")
      2. Ένας ΚΕΝΤΡΙΚΟΣ on_interaction listener (παρακάτω) πιάνει ΚΑΘΕ
         interaction και βάσει του custom_id αποφασίζει τι να κάνει.
    Έτσι όλα δουλεύουν persistent ακόμα και μετά από redeploy/restart.
"""

from __future__ import annotations

import discord
from discord import ui, app_commands
from discord.ext import commands

import config
from emojis import emoji
from utils import storage
from utils.permissions import has_roles
from utils.components import build_base_container, add_action_row, add_separator, add_text

STORE_NAME = "tickets"  # data/tickets.json


# =========================================================
# Ορισμός όλων των τύπων ticket (ανεξάρτητα από ποιο panel τα δείχνει)
# =========================================================
def _ticket_types() -> dict:
    return {
        "ownership": {
            "label": "Ownership",
            "emoji": emoji("tickets", "ownership"),
            "category_id": config.CAT_TICKET_OWNERSHIP_ID,
            "view_roles": [config.OWNERSHIP_ROLE_ID],
        },
        "report": {
            "label": "Report",
            "emoji": emoji("tickets", "report"),
            "category_id": config.CAT_TICKET_REPORT_ID,
            "view_roles": [config.OWNERSHIP_ROLE_ID, config.MANAGER_ROLE_ID],
        },
        "support": {
            "label": "Support",
            "emoji": emoji("tickets", "support"),
            "category_id": config.CAT_TICKET_SUPPORT_ID,
            "view_roles": config.STAFF_TEAM_ROLE_IDS,
        },
        "bug": {
            "label": "Bug Report",
            "emoji": emoji("tickets", "bug"),
            "category_id": config.CAT_TICKET_BUG_ID,
            "view_roles": [config.DEVELOPER_ROLE_ID, config.OWNERSHIP_ROLE_ID],
        },
        "anticheat": {
            "label": "Anticheat",
            "emoji": emoji("tickets", "anticheat"),
            "category_id": config.CAT_TICKET_ANTICHEAT_ID,
            "view_roles": [config.ANTICHEAT_MANAGER_ID, config.OWNERSHIP_ROLE_ID],
        },
        "reward": {
            "label": "Claim Your Reward",
            "emoji": emoji("tickets", "reward"),
            "category_id": config.CAT_TICKET_REWARD_ID,
            "view_roles": config.STAFF_TEAM_ROLE_IDS,  # περιλαμβάνει και το Ownership
        },
        "civilian_job": {
            "label": "Civilian Job",
            "emoji": emoji("jobs", "civilian"),
            "category_id": config.CAT_JOBS_ID,
            "view_roles": [config.CIVILIAN_MANAGER_ROLE_ID],
        },
        "criminal_job": {
            "label": "Criminal Job",
            "emoji": emoji("jobs", "criminal"),
            "category_id": config.CAT_JOBS_ID,
            "view_roles": [config.CRIMINAL_MANAGER_ROLE_ID],
        },
        "donate": {
            "label": "Donate",
            "emoji": emoji("donate", "donate"),
            "category_id": config.CAT_DONATE_ID,
            "view_roles": [config.OWNERSHIP_ROLE_ID, config.DONATE_MANAGER_ROLE_ID],
        },
    }


def _safe_name(text: str) -> str:
    text = text.lower().strip().replace(" ", "-")
    return "".join(c for c in text if c.isalnum() or c == "-")[:90]


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------
    # Δημιουργία ticket channel (κοινή λογική για ΟΛΑ τα είδη)
    # ---------------------------------------------------
    async def create_ticket(self, interaction: discord.Interaction, ticket_key: str):
        ttypes = _ticket_types()
        data = ttypes.get(ticket_key)
        if not data:
            await interaction.response.send_message("Άγνωστος τύπος ticket.", ephemeral=True)
            return

        guild = interaction.guild
        opener = interaction.user

        store = storage.get_store(STORE_NAME)
        for ch_id, info in store.items():
            if info.get("opener_id") == opener.id and info.get("type") == ticket_key:
                channel = guild.get_channel(int(ch_id))
                if channel:
                    await interaction.response.send_message(
                        f"Έχεις ήδη ανοιχτό ticket: {channel.mention}", ephemeral=True
                    )
                    return

        category = guild.get_channel(data["category_id"])
        if category is None:
            await interaction.response.send_message(
                "⚠️ Δεν βρέθηκε το category.", ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            opener: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_id in data["view_roles"]:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel_name = f"{ticket_key}-{_safe_name(opener.display_name)}"
        new_channel = await guild.create_text_channel(
            name=channel_name, category=category, overwrites=overwrites
        )

        store[str(new_channel.id)] = {
            "type": ticket_key,
            "opener_id": opener.id,
            "guild_id": guild.id,
        }
        storage.save(STORE_NAME, store)

        container = build_base_container(
            title=f"{data['emoji']} {data['label']} Ticket",
            description=f"Άνοιξε από: {opener.mention}\n Παρακαλόυμε περιμένετε λίγο και η ομάδα μας θα σας απαντήσει σύντομα.",
            color=discord.Colour.yellow(),
        )
        add_separator(container)
        close_btn = ui.Button(
            label="Close Ticket", style=discord.ButtonStyle.danger,
            emoji=emoji("tickets", "close"), custom_id=f"ticket_close:{new_channel.id}",
        )
        ping_btn = ui.Button(
            label="Ping User", style=discord.ButtonStyle.secondary,
            emoji=emoji("tickets", "ping"), custom_id=f"ticket_ping:{new_channel.id}",
        )
        add_action_row(container, close_btn, ping_btn)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await new_channel.send(view=view)

        log_channel = guild.get_channel(config.LOG_TICKETS_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title=f"{emoji('tickets', 'ticket')} Ticket Opened",
                color=discord.Colour.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Τύπος", value=data["label"], inline=True)
            embed.add_field(name="Channel", value=new_channel.mention, inline=True)
            embed.add_field(name="Άνοιξε από", value=f"{opener.mention} (`{opener.id}`)", inline=False)
            await log_channel.send(embed=embed)

        await interaction.response.send_message(f"✅ Το ticket σου: {new_channel.mention}", ephemeral=True)

    # ---------------------------------------------------
    # Κλείσιμο ticket
    # ---------------------------------------------------
    async def handle_close(self, interaction: discord.Interaction, channel_id: int):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(channel_id))
        if not info:
            await interaction.response.send_message("Αυτό το ticket δεν υπάρχει πια.", ephemeral=True)
            return

        if interaction.user.id == info["opener_id"]:
            await interaction.response.send_message(
                "Δεν μπορείς να κλείσεις το δικό σου ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message("🔒 Το ticket κλείνει σε 5 δευτερόλεπτα...", ephemeral=False)

        log_channel = interaction.guild.get_channel(config.LOG_TICKETS_CHANNEL_ID)
        if log_channel:
            ttypes = _ticket_types()
            type_label = ttypes.get(info["type"], {}).get("label", info["type"])
            embed = discord.Embed(
                title=f"{emoji('tickets', 'close')} Ticket Closed",
                color=discord.Colour.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Τύπος", value=type_label, inline=True)
            embed.add_field(name="Channel", value=f"`#{interaction.channel.name}`", inline=True)
            embed.add_field(name="Άνοιξε από", value=f"<@{info['opener_id']}>", inline=False)
            embed.add_field(name="Έκλεισε από", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
            await log_channel.send(embed=embed)

        store.pop(str(channel_id), None)
        storage.save(STORE_NAME, store)
        await discord.utils.sleep_until(discord.utils.utcnow() + __import__("datetime").timedelta(seconds=5))
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            await channel.delete(reason=f"Ticket closed by {interaction.user}")

    # ---------------------------------------------------
    # Ping User
    # ---------------------------------------------------
    async def handle_ping_user(self, interaction: discord.Interaction, channel_id: int):
        store = storage.get_store(STORE_NAME)
        info = store.get(str(channel_id))
        if not info:
            await interaction.response.send_message("Αυτό το ticket δεν υπάρχει πια.", ephemeral=True)
            return

        if not has_roles(interaction.user, config.STAFF_TEAM_ROLE_IDS):
            await interaction.response.send_message("⛔ Μόνο το staff team μπορεί να κάνει ping τον χρήστη.", ephemeral=True)
            return

        if interaction.user.id == info["opener_id"]:
            await interaction.response.send_message("Δεν μπορείς να κάνεις ping τον εαυτό σου.", ephemeral=True)
            return

        opener = interaction.guild.get_member(info["opener_id"])
        await interaction.response.send_message(f"🔔 {opener.mention if opener else ''}", ephemeral=False)
        if opener:
            try:
                await opener.send(f"🔔 Έχεις ειδοποίηση στο ticket σου: {interaction.channel.mention}")
            except discord.Forbidden:
                pass

    # ---------------------------------------------------
    # Κεντρικός interaction listener (persistent components)
    # ---------------------------------------------------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id", "")

        if custom_id == "support_ticket_select":
            value = interaction.data["values"][0]
            await self.create_ticket(interaction, value)
        elif custom_id == "ticket_open_civilian_job":
            await self.create_ticket(interaction, "civilian_job")
        elif custom_id == "ticket_open_criminal_job":
            await self.create_ticket(interaction, "criminal_job")
        elif custom_id == "ticket_open_donate":
            await self.create_ticket(interaction, "donate")
        elif custom_id.startswith("ticket_close:"):
            channel_id = int(custom_id.split(":")[1])
            await self.handle_close(interaction, channel_id)
        elif custom_id.startswith("ticket_ping:"):
            channel_id = int(custom_id.split(":")[1])
            await self.handle_ping_user(interaction, channel_id)

    # ---------------------------------------------------
    # Slash commands - στέλνουν τα panels
    # ---------------------------------------------------
    @app_commands.command(name="panel-support", description="Στέλνει το Support ticket panel")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID, config.MANAGER_ROLE_ID, config.STAFF_ROLE_ID)
    async def panel_support(self, interaction: discord.Interaction):
        ttypes = _ticket_types()
        container = build_base_container(
            title="Warzone Reborn Roleplay - Tickets",
            description="Επίλεξε κατηγορία από το μενού παρακάτω για να ανοίξεις το ticket που θές. Πές μας τι χρειάζεσαι και θα σε εξυπηρετίσουμε πολύ σύντομα.",
            banner_url=config.TICKET_SUPPORT_BANNER_URL,
            thumbnail_url=config.TICKET_SUPPORT_THUMBNAIL_URL,
        )
        add_separator(container)
        _descriptions = {
            "ownership": "Επικοινωνία αποκλειστικά με το Ownership",
            "report": "Καταγγελία παίκτη ή μέλους staff",
            "support": "Γενική υποστήριξη & ερωτήσεις",
            "bug": "Αναφορά σφάλματος στο server ή bot",
            "anticheat": "Αναφορά περιστατικού cheat/exploit",
            "reward": "Διεκδίκησε το reward σου",
        }
        options = [
            discord.SelectOption(
                label=ttypes[k]["label"],
                value=k,
                emoji=ttypes[k]["emoji"] or None,
                description=_descriptions.get(k, ""),
            )
            for k in ("ownership", "report", "support", "bug", "anticheat", "reward")
        ]
        select = ui.Select(placeholder="Επίλεξε κατηγορία...", options=options, custom_id="support_ticket_select")
        add_action_row(container, select)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await interaction.channel.send(view=view)
        await interaction.response.send_message("✅ Στάλθηκε.", ephemeral=True)

    @app_commands.command(name="panel-civilian-job", description="Στέλνει το Civilian Job panel")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID, config.MANAGER_ROLE_ID, config.STAFF_ROLE_ID)
    async def panel_civilian_job(self, interaction: discord.Interaction):
        await self._send_button_panel(
            interaction, key="civilian_job", title="Warzone Reborn Roleplay - Civilian Job Ticket",
            description="Πάτησε το κουμπί και επικοινώνησε με τον αρμόδιο Manager για να πάρεις το civilian job σου.",
        )

    @app_commands.command(name="panel-criminal-job", description="Στέλνει το Criminal Job panel")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID, config.MANAGER_ROLE_ID, config.STAFF_ROLE_ID)
    async def panel_criminal_job(self, interaction: discord.Interaction):
        await self._send_button_panel(
            interaction, key="criminal_job", title="Warzone Reborn Roleplay - Criminal Job Ticket",
            description="Πάτησε το κουμπί και επικοινώνησε με τον αρμόδιο Manager για να πάρεις το criminal job σου.",
        )

    @app_commands.command(name="panel-donate", description="Στέλνει το Donate panel")
    @app_commands.checks.has_any_role(config.OWNERSHIP_ROLE_ID, config.MANAGER_ROLE_ID, config.STAFF_ROLE_ID)
    async def panel_donate(self, interaction: discord.Interaction):
        ttypes = _ticket_types()
        data = ttypes["donate"]

        container = build_base_container(
            title="Donate Terms & Information",
            description=(
                "Όταν κάνετε Donate υποστηρίζετε την λειτουργία και την ανάπτυξη του server, βοηθώντας μας να τον κρατάμε ενεργό και να τον βελτιώνουμε συνεχώς. "
                "Παρόλα αυτά, όλοι οι παίκτες αντιμετωπίζονται το ίδιο ανεξάρτητα από το αν έχουν κάνει Donate ή όχι. "
                "Το Donate αποτελεί καθαρά προαιρετική δωρεά και δεν είναι απαραίτητο για να παίξετε στον server. "
                "Μετά την ολοκλήρωση μιας δωρεάς δεν υπάρχει δυνατότητα επιστροφής χρημάτων ή αλλαγής του πακέτου."
            ),
            banner_url=config.TICKET_DONATE_BANNER_URL,
            thumbnail_url=config.TICKET_DONATE_THUMBNAIL_URL,
        )
        add_separator(container)
        add_text(container, (
            "> Όλα τα Donates παραμένουν ενεργά μέχρι το ενδεχόμενο κλείσιμο του server. "
            "Δεν υπάρχει δυνατότητα επιστροφής μετά από Wipe ή σε περίπτωση που κάποιος τιμωρηθεί με Ban.\n"
            "> Απαγορεύεται αυστηρά η πώληση, ανταλλαγή ή μεταβίβαση Donate (είτε με πραγματικά χρήματα είτε με ingame χρήματα/αντικείμενα). "
            "Σε περίπτωση παραβίασης, το Donate αφαιρείται χωρίς προειδοποίηση.\n"
            "> Για να διατηρήσετε κάποιο Civilian ή Criminal Donate Job πρέπει να είστε ενεργοί στον server. "
            "Αν ένα job παραμείνει ανενεργό για μεγάλο χρονικό διάστημα, μπορεί να αφαιρεθεί μετά από προειδοποίηση."
        ))
        add_separator(container)
        add_text(container, (
            "## Payment Methods\n"
            "Οι διαθέσιμοι τρόποι πληρωμής για Donate στον server είναι:\n"
            "> PayPal (Euro)\n"
            "> Prepaid Paysafecard (Ελληνική)"
        ))
        add_separator(container)
        add_text(container, (
            "## Πώς να κάνετε Donate;\n"
            "Για να πραγματοποιήσετε Donate μπορείτε να μπείτε στο παρακάτω κανάλι:\n"
            "https://discord.com/channels/1519656885534457960/1528897152275714138"
            "Εκεί μπορείτε να περιμένετε κάποιο μέλος <@&1519675834426724383> ή να ανοίξετε ένα Donate Ticket για εξυπηρέτηση. "
            "Σε περίπτωση πληρωμής μέσω Paysafecard είναι απαραίτητο να στείλετε και φωτογραφία του αποκόμματος. "
            "Ο χρόνος εξυπηρέτησης συνήθως κυμαίνεται μεταξύ **24 έως 48 ωρών**.\n\n"
            "```Για πιο γρήγορη εξυπηρέτηση προτείνεται να ανοίξετε ένα ticket ώστε να μιλήσετε απευθείας με κάποιον υπεύθυνο για την διαδικασία Donate.```"
        ))
        add_separator(container)
        btn = ui.Button(
            label="Donate Ticket", style=discord.ButtonStyle.success,
            emoji=data["emoji"] or None, custom_id="ticket_open_donate",
        )
        add_action_row(container, btn)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await interaction.channel.send(view=view)
        await interaction.response.send_message("✅ Στάλθηκε.", ephemeral=True)

    async def _send_button_panel(self, interaction: discord.Interaction, *, key: str, title: str, description: str):
        ttypes = _ticket_types()
        data = ttypes[key]
        banner = {
            "civilian_job": config.TICKET_JOBS_BANNER_URL,
            "criminal_job": config.TICKET_JOBS_BANNER_URL,
            "donate": config.TICKET_DONATE_BANNER_URL,
        }[key]
        thumb = {
            "civilian_job": config.TICKET_JOBS_THUMBNAIL_URL,
            "criminal_job": config.TICKET_JOBS_THUMBNAIL_URL,
            "donate": config.TICKET_DONATE_THUMBNAIL_URL,
        }[key]

        container = build_base_container(title=title, description=description, banner_url=banner, thumbnail_url=thumb)
        add_separator(container)
        btn = ui.Button(
            label=data["label"], style=discord.ButtonStyle.success,
            emoji=data["emoji"] or None, custom_id=f"ticket_open_{key}",
        )
        add_action_row(container, btn)

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await interaction.channel.send(view=view)
        await interaction.response.send_message("✅ Στάλθηκε.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
