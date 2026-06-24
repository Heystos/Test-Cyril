#!/usr/bin/env python3
"""Send a test push notification to verify ntfy setup."""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
if not NTFY_TOPIC:
    print("Erreur : NTFY_TOPIC manquant dans .env")
    sys.exit(1)

title = "⚽ France 2–1 Brésil | FT"
body = (
    "🏆 Coupe du Monde 2026 · FINALE\n"
    "\n"
    "Buteurs:\n"
    "France: Mbappé 34' (pen), Dembélé 67'\n"
    "Brésil: Vinicius Jr. 12'"
)

resp = requests.post(
    f"https://ntfy.sh/{NTFY_TOPIC}",
    data=body.encode("utf-8"),
    headers={
        "Title": title.encode("utf-8"),
        "Priority": "high",
        "Tags": "soccer,trophy",
        "Content-Type": "text/plain; charset=utf-8",
    },
    timeout=10,
)
resp.raise_for_status()
print(f"✅ Notification de test envoyée sur le topic '{NTFY_TOPIC}'")
print("Vérifiez votre iPhone — la notification devrait arriver dans quelques secondes.")
