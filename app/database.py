from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL za bazu podataka - koristimo SQLite za jednostavnost u razvoju
SQLALCHEMY_DATABASE_URL = "sqlite:///./datacenter.db"

# Kreiramo engine za konekciju sa bazom
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Konfiguracija sesije za upite ka bazi
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Baza klasa za SQLAlchemy modele
Base = declarative_base()

# Funkcija za dependency injection - obezbeđuje sesiju za svaki zahtev
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()