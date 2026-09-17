from flask_alembic import Alembic
from flask_cors import CORS
from flask_smorest import Api
from flask_sqlalchemy import SQLAlchemy
from flask_debugtoolbar import DebugToolbarExtension
from flask_admin import Admin

admin = Admin()
alembic = Alembic()
cors = CORS()
db = SQLAlchemy()
api = Api()
debugtoolbar = DebugToolbarExtension()