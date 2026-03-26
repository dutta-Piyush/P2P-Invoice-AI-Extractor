import logging
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "procurement.db"
_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created at %s", _DB_PATH)


# Column migrations: list of (table, column, DDL type) to ensure exist.
# Add a new entry here whenever a column is added to an ORM model.
_REQUIRED_COLUMNS: list[tuple[str, str, str]] = [
    ("requests", "source_pdf", "VARCHAR(500)"),
]


def migrate_schema() -> None:
    """Idempotently add any missing columns and repair the request counter."""
    with engine.connect() as conn:
        # 1. Add any missing columns
        for table, column, col_type in _REQUIRED_COLUMNS:
            rows = conn.execute(text("PRAGMA table_info(:tbl)".replace(":tbl", table))).fetchall()
            existing = {row[1] for row in rows}
            if column not in existing:
                # Values come from the hardcoded _REQUIRED_COLUMNS constant above, not user input.
                stmt = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"  # noqa: S608
                conn.execute(text(stmt))
                conn.commit()
                logger.info("Schema migration applied: %s.%s (%s)", table, column, col_type)

        # 2. Ensure request_counter is seeded from the actual max request ID.
        try:
            row = conn.execute(text("SELECT last_value FROM request_counter WHERE id = 1")).fetchone()
        except Exception:
            logger.warning("request_counter table not ready — skipping counter sync")
            return
        max_row = conn.execute(
            text("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM requests")
        ).fetchone()
        max_seq = max_row[0] or 0
        if row is None:
            conn.execute(text("INSERT INTO request_counter (id, last_value) VALUES (1, :v)"), {"v": max_seq})
            conn.commit()
            logger.info("Request counter initialised to %d", max_seq)
        elif row[0] < max_seq:
            conn.execute(text("UPDATE request_counter SET last_value = :v WHERE id = 1"), {"v": max_seq})
            conn.commit()
            logger.info("Request counter resynced to %d (was %d)", max_seq, row[0])


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
