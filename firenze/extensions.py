from flask_alembic import Alembic
from flask_cors import CORS
from flask_smorest import Api
from flask_sqlalchemy import SQLAlchemy

alembic = Alembic()
cors = CORS()
db = SQLAlchemy()
api = Api()
