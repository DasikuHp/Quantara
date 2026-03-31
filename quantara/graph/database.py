import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quantara.config import DB_PATH
from quantara.graph.models import Base

# Módulo Database (Graph)
# Responsabilidad: Gestión de la conexión y sesiones con la base de datos (SQLite)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Crea todas las tablas en la base de datos si no existen."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    from quantara.graph import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
