import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_URL = "sqlite:///comicprice.db"


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or os.environ.get("COMICPRICE_DB", DEFAULT_URL), future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session(engine: Engine) -> Session:
    return sessionmaker(engine, expire_on_commit=False)()
