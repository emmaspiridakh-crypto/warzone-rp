"""
utils/components.py
---------------------
Βοηθητικές συναρτήσεις για χτίσιμο Components V2 panels (discord.py >= 2.6).

Δομή που χρησιμοποιούμε παντού:
    Container
        -> MediaGallery (banner, optional)
        -> Section (text + thumbnail accessory, optional) ή απλό TextDisplay
        -> Separator
        -> ActionRow(s) με Buttons / Select menus

Κάθε panel cog χτίζει το δικό του discord.ui.LayoutView, αλλά χρησιμοποιεί
αυτές τις γενικές συναρτήσεις ώστε να μην ξαναγράφουμε το ίδιο boilerplate.
"""

from __future__ import annotations

import discord
from discord import ui


def build_base_container(
    *,
    title: str,
    description: str = "",
    banner_url: str | None = None,
    thumbnail_url: str | None = None,
     color: discord.Colour = discord.Colour.from_str("#FEE75C"),
) -> ui.Container:
    """Φτιάχνει ένα Container με optional banner πάνω-πάνω + τίτλο/περιγραφή
    (με optional thumbnail δίπλα)."""
    container = ui.Container(accent_colour=color)

    if banner_url:
        container.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=banner_url)))

    header_text = f"## {title}"
    if description:
        header_text += f"\n{description}"

    if thumbnail_url:
        section = ui.Section(accessory=ui.Thumbnail(media=thumbnail_url))
        section.add_item(ui.TextDisplay(header_text))
        container.add_item(section)
    else:
        container.add_item(ui.TextDisplay(header_text))

    return container


def add_separator(container: ui.Container, *, spacing: discord.SeparatorSpacing = discord.SeparatorSpacing.small) -> None:
    container.add_item(ui.Separator(spacing=spacing))


def add_text(container: ui.Container, text: str) -> None:
    container.add_item(ui.TextDisplay(text))


def add_action_row(container: ui.Container, *items: ui.Item) -> ui.ActionRow:
    """Δημιουργεί ActionRow, βάζει μέσα τα items (buttons/selects) και το προσθέτει
    στο container. Επιστρέφει το ActionRow σε περίπτωση που θες reference."""
    row = ui.ActionRow()
    for item in items:
        row.add_item(item)
    container.add_item(row)
    return row


def add_section_with_button(
    container: ui.Container,
    *,
    text: str,
    button: ui.Button,
) -> ui.Section:
    """Section: αριστερά κείμενο, δεξιά (accessory) ένα button.
    Χρησιμοποιείται στο application panel (λίστα με Apply buttons)."""
    section = ui.Section(accessory=button)
    section.add_item(ui.TextDisplay(text))
    container.add_item(section)
    return section


class SimpleLayoutView(ui.LayoutView):
    """Γενικό LayoutView wrapper - απλά τυλίγει ένα container.
    timeout=None ώστε τα buttons να δουλεύουν για πάντα (persistent),
    ΑΡΚΕΙ να γίνει bot.add_view() στο on_ready με το ίδιο custom_id."""

    def __init__(self, container: ui.Container):
        super().__init__(timeout=None)
        self.add_item(container)
