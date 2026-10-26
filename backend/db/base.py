from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

metadata = MetaData(schema="auth")

class Base(DeclarativeBase):
    metadata = metadata

from models import user
from models import jwt_token_blacklist