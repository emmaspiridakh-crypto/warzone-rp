"""
keep_alive.py
--------------
Ένα ψεύτικο (fake) Flask web server που τρέχει παράλληλα με το bot.
Λόγος ύπαρξης:
  - Το Render.com (Web Service) θέλει να "ακούει" σε ένα port, αλλιώς killάρει το deployment.
  - Το UptimeRobot κάνει ping σε αυτό το endpoint κάθε X λεπτά ώστε το Render
    να μη το βάλει σε sleep / να μην το θεωρήσει νεκρό.

Δεν εξυπηρετεί καμία λειτουργία του bot, είναι ΜΟΝΟ για να κρατάει το process ζωντανό.
"""

import os
import threading
from flask import Flask

app = Flask(__name__)

# Render σου δίνει port μέσω env var PORT. Βάζουμε 1000 ως fallback (fake port)
# αν τρέξεις local. Στο Render απλά SET-άρεται αυτόματα το PORT.
FAKE_PORT = int(os.environ.get("PORT", 1000))


@app.route("/")
def home():
    return "Bot is alive!", 200


@app.route("/health")
def health():
    return {"status": "ok"}, 200


def run():
    # host=0.0.0.0 ΑΠΑΡΑΙΤΗΤΟ για Render, αλλιώς δεν βλέπει το port ανοιχτό
    app.run(host="0.0.0.0", port=FAKE_PORT)


def keep_alive():
    """Καλείται μία φορά από το main.py πριν το bot.run()."""
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()
