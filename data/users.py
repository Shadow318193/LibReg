import sqlalchemy as db
from .db_session import SqlAlchemyBase
from sqlalchemy import orm

from flask_login import UserMixin

from datetime import datetime

from __shop_config import DEFAULT_THEME


class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False, index=True)
    email = db.Column(db.String, nullable=True, index=True)
    phone = db.Column(db.String, nullable=False, unique=True, index=True)
    name = db.Column(db.String, nullable=False)
    address = db.Column(db.String, nullable=True)
    hashed_password = db.Column(db.String, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_moderator = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String, default=DEFAULT_THEME)
    creation_date = db.Column(db.DateTime, default=datetime.now)
    last_auth = db.Column(db.DateTime, default=datetime.now)

    product = orm.relation("Product", back_populates="user")
    order = orm.relation("Order", back_populates="user")

    def __repr__(self):
        return f"Пользователь '{self.name}' (ID - {self.id})"
