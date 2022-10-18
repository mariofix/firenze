from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from firenze.config import settings
from sqlalchemy_repr import RepresentableBase

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL, pool_recycle=1800, pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base(cls=RepresentableBase)
