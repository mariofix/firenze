from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy_repr import RepresentableBase

from firenze.config import Settings

engine = create_engine(Settings.SQLALCHEMY_DATABASE_URL, pool_recycle=1800, pool_pre_ping=True)
SessionLocal = sessionmaker(autoflush=True, bind=engine)

Base = declarative_base(cls=RepresentableBase)
