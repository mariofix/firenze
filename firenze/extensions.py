from flask_admin import Admin

# from flask_admin.theme import TablerTheme
from flask_admin_tabler import TablerTheme
from flask_babel import Babel
from flask_cors import CORS
from flask_debugtoolbar import DebugToolbarExtension
from flask_migrate import Migrate
from flask_smorest import Api
from flask_sqlalchemy import SQLAlchemy

theme = TablerTheme(theme_layout="fluid", theme_primary="red", theme_radius="2")
admin = Admin(name="Firenze Admin", theme=theme)
migrate = Migrate()
cors = CORS()
db = SQLAlchemy()
api = Api()
debugtoolbar = DebugToolbarExtension()
babel = Babel()
