import os

from dotenv import load_dotenv

from firenze import create_app

load_dotenv()

app = create_app(os.getenv("FIRENZE_SETTINGS", "firenze.settings"))
