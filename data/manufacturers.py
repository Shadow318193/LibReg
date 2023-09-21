import sqlalchemy as db
from .db_session import SqlAlchemyBase
from sqlalchemy import orm

from datetime import datetime


class Manufacturer(SqlAlchemyBase):
    __tablename__ = 'manufacturers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False, index=True)
    name = db.Column(db.String, nullable=False)
    about = db.Column(db.String, nullable=False)
    logo = db.Column(db.String, nullable=False)
    logo_preview = db.Column(db.String, nullable=True)
    poster_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.now)
    toggle = db.Column(db.Boolean, nullable=False, default=True)

    user = orm.relation("User")
    product = orm.relation("Product", back_populates="manufacturer")

    def __repr__(self):
        return f"Производитель '{self.name}' (ID - {self.id})"
