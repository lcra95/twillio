import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

load_dotenv()
env = os.environ

DATABASE_URL = (
    f"mysql+mysqlconnector://{env.get('DB_USER')}:{env.get('DB_PASSWORD')}"
    f"@{env.get('DB_HOST')}:{env.get('DB_PORT')}/{env.get('DB_NAME')}"
)

engine = create_engine(
    DATABASE_URL,
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
