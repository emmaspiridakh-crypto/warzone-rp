# RP Discord Bot — Πλήρης Οδηγός

Python + discord.py (Components V2) + Flask (Render) + UptimeRobot.

## Δομή Project

```
config.py           όλα τα IDs (roles/categories/channels/banners) + ερωτήσεις applications
emojis.py            custom emojis χωρισμένα ανά κατηγορία (static + animated)
main.py              entry point, intents, φόρτωση cogs
keep_alive.py         fake Flask server για Render/UptimeRobot
utils/
  components.py       helpers για Components V2 (Container, Section, Buttons κλπ)
  permissions.py       role checks
  storage.py            JSON persistence (data/*.json)
cogs/
  tickets.py            Support (dropdown) + Civilian/Criminal Job + Donate (button)
  suggestions.py         auto suggestion system (upvote/downvote)
  moderation.py           ban/unban/kick/timeout/untimeout/clearmessages/say/say2/dmall
  temp_voice.py            join-to-create temp voice channels
  staff_activity.py         on-duty tracking + leaderboard panel
  logging_events.py          join/leave, roles, channels, messages, voice logs
  applications.py             ΕΛΑΣ/ΕΚΑΒ/Στρατός/Staff/Manager applications
  server_status.py             live stats σε voice channels
  panel_command.py              !panel (λίστα εντολών)
```

## ⚠️ ΥΠΟΧΡΕΩΤΙΚΟ Checklist πριν τρέξεις το bot

### 1. config.py — IDs
- [ ] `GUILD_ID`
- [ ] Όλα τα **ROLES** (Ownership, Manager, Staff, Developer, Civilian Manager, Criminal Manager, Donate Manager, Founder, On Duty, Waiting for Interview)
- [ ] **4 categories** για support tickets (Ownership/Report/Support/Bug — ξεχωριστά)
- [ ] **1 category** για Jobs (civilian + criminal μαζί)
- [ ] **1 category** για Donate
- [ ] `STAFF_PING_CHANNEL_ID` (ping όταν ανοίγει ticket ή temp voice)
- [ ] `SUGGESTIONS_CHANNEL_ID`
- [ ] `TEMP_VOICE_JOIN_CHANNEL_ID` + `TEMP_VOICE_CATEGORY_ID`
- [ ] `STAFF_ACTIVITY_VOICE_CHANNEL_ID` + `STAFF_ACTIVITY_PANEL_CHANNEL_ID` + `STAFF_ACTIVITY_LOG_CHANNEL_ID`
- [ ] Όλα τα **LOG channels** (join/leave, roles, channels, messages, voice, applications + 7 command logs)
- [ ] `APPLICATIONS_PANEL_CHANNEL_ID` + `APPLICATIONS_CATEGORY_ID`
- [ ] Ερωτήσεις μέσα στο `APPLICATION_TYPES` (ΕΛΑΣ/ΕΚΑΒ/Στρατός/Staff/Manager)
- [ ] 4 **voice channels** για server status (members/online/boosts/bots)
- [ ] Όλα τα **banner/thumbnail URLs** (ανέβασέ τα κάπου π.χ. Discord CDN / imgur και βάλε το link)

### 2. emojis.py — Custom Emojis
- [ ] Βάλε IDs σε ΟΛΑ τα emoji placeholders (`<:name:000...>` ή `<a:name:000...>` για animated)

### 3. Discord Developer Portal
- [ ] Ενεργοποίησε **SERVER MEMBERS INTENT**
- [ ] Ενεργοποίησε **PRESENCE INTENT**
- [ ] Ενεργοποίησε **MESSAGE CONTENT INTENT**
(Bot → Privileged Gateway Intents)

### 4. Bot Permissions στο server
Χρειάζεται: Manage Channels, Manage Roles, Manage Messages, Kick Members, Ban Members,
Moderate Members (timeout), Send Messages, Embed Links, Use External Emojis, Connect, Move Members.
⚠️ Ο ρόλος του bot πρέπει να είναι ΨΗΛΟΤΕΡΑ από όλους τους ρόλους που θα διαχειρίζεται (On Duty, Waiting for Interview κλπ) στη λίστα ρόλων του server.

### 5. Render / UptimeRobot
Δες το `README_DEPLOY.md`.

## Σημειώσεις
- Τα persistent buttons δουλεύουν μέσω ενός κεντρικού `on_interaction` listener σε κάθε cog
  (διαβάζει το `custom_id`), όχι μέσω registered Views — έτσι όλα επιβιώνουν σε restart/redeploy.
- Το `data/` φτιάχνεται αυτόματα. Στο Render free tier ΔΕΝ είναι persistent ανάμεσα σε deploys
  (staff activity totals/suggestion votes μηδενίζονται σε κάθε redeploy). Αν το θες μόνιμο,
  χρειάζεται πραγματική βάση δεδομένων.
- Αν αλλάξει κάτι στο discord.py Components V2 API (είναι σχετικά νέο feature), ίσως χρειαστεί
  μικρή προσαρμογή στο `utils/components.py`.
