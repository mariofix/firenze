from firenze import create_app
import os
from dotenv import load_dotenv

load_dotenv()

app = create_app(os.getenv("FIRENZE_SETTINGS", "firenze.settings"))
