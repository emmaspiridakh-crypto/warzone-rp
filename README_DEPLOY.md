# RP Discord Bot — Render Deployment Notes

## Τι πρέπει να υπάρχει στο repo (GitHub) για να γίνει deploy στο Render

```
repo/
├── main.py
├── keep_alive.py
├── config.py
├── emojis.py
├── requirements.txt
├── Dockerfile
├── .gitignore
├── utils/
│   ├── __init__.py
│   ├── components.py
│   ├── permissions.py
│   └── storage.py
├── cogs/
│   ├── __init__.py
│   ├── tickets.py
│   ├── suggestions.py
│   ├── moderation.py
│   ├── temp_voice.py
│   ├── staff_activity.py
│   ├── logging_events.py
│   ├── applications.py
│   ├── server_status.py
│   └── panel_command.py
└── data/            <-- άδειος φάκελος, χρειάζεται .gitkeep γιατί το git δεν ανεβάζει άδειους φακέλους
    └── .gitkeep
```

## Render setup (βήματα)

1. **New + → Web Service** (όχι Background Worker — θέλουμε port binding για το UptimeRobot)
2. Connect το GitHub repo σου
3. **Environment**: Docker
4. **Region**: ό,τι είναι πιο κοντά σου
5. **Instance Type**: Free (αρκεί για bot + fake Flask server)
6. **Environment Variables** (Render → Environment):
   - `DISCORD_TOKEN` = το token του bot σου
   - `PORT` βάζεται **αυτόματα** από το Render, δεν το πειράζεις
7. Deploy. Στα logs πρέπει να δεις και `Flask` να ξεκινάει και `Bot is ready` (ή ό,τι print βάλουμε στο main.py)

## UptimeRobot setup

1. New Monitor → **HTTP(s)**
2. URL: το public URL που σου δίνει το Render (κάτι σε `https://xxxxx.onrender.com/`)
3. Interval: 5 λεπτά (το Free plan του Render κοιμίζει το service μετά από ~15 λεπτά αδράνειας, οπότε 5' interval είναι ασφαλές)
4. Save — αυτό κρατάει το bot ζωντανό 24/7 χωρίς να χρειάζεται paid plan

## .env (μόνο για local testing — ΔΕΝ ανεβαίνει στο GitHub)

```
DISCORD_TOKEN=your_token_here
```

⚠️ Το `.env` είναι ήδη στο `.gitignore`. Στο Render βάζεις το token ως Environment Variable, όχι ως αρχείο.
