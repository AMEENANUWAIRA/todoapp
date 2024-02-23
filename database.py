from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

PG_DB_URL = 'postgresql://postgres:postgres@localhost/TodoAppDB'

engine = create_engine(PG_DB_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database object creation
Base = declarative_base()


class TodoRequest(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=3, max_length=100)
    priority: int = Field(gt=0, lt=6)
    complete: bool = Field(default=False)
