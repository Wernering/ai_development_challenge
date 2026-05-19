import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.models import Base


def get_engine(db_path: str):
    db_dir = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_dir, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


def get_session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


_AI_COLUMNS = [
    ("ai_classification", "TEXT"),
    ("ai_root_cause", "TEXT"),
    ("ai_recommendation", "TEXT"),
]


def init_db(engine) -> None:
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for col_name, col_type in _AI_COLUMNS:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE alerts ADD COLUMN {col_name} {col_type}"
                    )
                )
                conn.commit()
            except Exception:
                pass


@contextmanager
def get_db(session_factory):
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
