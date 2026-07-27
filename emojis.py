"""
emojis.py
---------
Custom emojis χωρισμένα ανά κατηγορία.

ΠΩΣ ΤΟ ΣΥΜΠΛΗΡΩΝΕΙΣ:
- Static emoji:   "<:name:ID>"
- Animated emoji: "<a:name:ID>"   (πρόσεξε το "a" πριν τα δύο κόλον)

Το "name" δεν χρειάζεται να ταιριάζει 100% με το πραγματικό όνομα του emoji,
αλλά καλό είναι να το αφήσεις ίδιο για ευκολία. Το μόνο που μετράει στην
εμφάνιση είναι το σωστό ID.

Χρήση μέσα στον κώδικα:
    from emojis import emoji
    emoji("tickets", "close")
"""

EMOJIS = {
    "tickets": {
        "ownership": "<:ownership:1528824025600622632>",
        "report": "<a:report:1528885796159885503>",
        "support": "<a:support:1528885660340195470>",
        "bug": "<:bug:1528885729730498761>",
        "anticheat": "<:anticheat:1528886656982323301>",
        "close": "<:close:1528886394288865421>",
        "ping": "<a:ping:1528886230190919800>",
        "ticket": "<:ticket:1528885002836644152>",
        "reward": "<:reward:1529408322275512340>",  # PLACEHOLDER: βάλε custom emoji αν θες
    },
    "jobs": {
        "civilian": "<:civilian:1528885189017866300>",
        "criminal": "<a:criminal:1528886482557730969>",
    },
    "donate": {
        "donate": "<a:donate:1528887083463213206>",  # παράδειγμα animated
    },
    "suggestions": {
        "upvote": "<:upvote:1528885896374390956>",
        "downvote": "<:downvote:1528885977249087750>",
    },
    "moderation": {
        "ban": "<a:ban:1528885432950198472>",
        "unban": "<a:unban:1528885432950198472>",
        "kick": "<a:kick:1528885337877647491>",
        "timeout": "<a:timeout:1528885337877647491>",
        "untimeout": "<a:untimeout:1528885337877647491>",
        "clear": "<:clear:1528886566389289131>",
    },
    "voice": {
        "join": "<a:voice_join:1528887355698581697>",
        "leave": "<a:voice_leave:1528887254981017705>",
        "temp": "<a:temp_voice:1528885660340195470>",
    },
    "staff_activity": {
        "on_duty": "<a:on_duty:1528887355698581697>",
        "off_duty": "<a:off_duty:1528887254981017705>",
        "leaderboard": "<:leaderboard:1528824025600622632>",
    },
    "applications": {
        "elas": "<:elas:1520566656370217010>",
        "ekab": "<:ekab:1528884760305205248>",
        "staff": "<:staff:1528888125223604306>",
        "limeniko": "<:limeniko:1528888709020123348>",
        "fbi":     "<:fbi:1528888032735006730>",
        "manager": "<:manager:1528887937276575747>",
        "accept": "<:accept:1528886311820197918>",
        "deny": "<:deny:1528886394288865421>",
        "apply": "<:apply:1528824025600622632>",
        "send": "<:send:1528886311820197918>",
        "ping_staff": "<a:ping_staff:1528886230190919800>",
    },
    "panel": {
        "list": "<:list:1528886566389289131>",
    },
"giveaway": {
    "giveaway":      "<a:giveaway:1529407370416099398>",
    "join":          "<:gw_join:1529410479233962026>",
    "leave":         "<:gw_leave:1529410448649355366>",
    "info":          "<:gw_info:1529410422841675867>",
    "edit":          "<:gw_edit:1528887760977662012>",
    "reroll":        "<:gw_reroll:1529409770279145493>",
    "end":           "<a:gw_end:1528887254981017705>",
    "participants":  "<:gw_participants:1529409844514258994>",
    "winner":        "<:gw_winner:1529407419778596874>",
    "prize":         "<a:gw_prize:1529407370416099398>",
    "host":          "<:gw_host:1529409206699167905>",
    "winners_count": "<a:gw_winners:1529410389283045376>",
    "entries":       "<:gw_entries:1529409844514258994>",
    "time":          "<a:gw_time:1529409247530582016>",
    "id":            "<:gw_id:1529408099394257026>",
    "role":          "<:gw_role:1528824025600622632>",
    },
}


def emoji(category: str, name: str) -> str:
    """Επιστρέφει το emoji string. Αν δεν βρεθεί, επιστρέφει κενό string (δεν σκάει το bot)."""
    try:
        return EMOJIS[category][name]
    except KeyError:
        return ""
