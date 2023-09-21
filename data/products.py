import sqlalchemy as db
from .db_session import SqlAlchemyBase
from sqlalchemy import orm

from datetime import datetime


class Product(SqlAlchemyBase):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False, index=True)
    name = db.Column(db.String, nullable=False)
    about = db.Column(db.String, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    images = db.Column(db.String, nullable=False)
    image_preview = db.Column(db.String, nullable=True)
    tags = db.Column(db.String, nullable=False)
    poster_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    manufacturer_id = db.Column(db.Integer, db.ForeignKey("manufacturers.id"), nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.now)
    toggle = db.Column(db.Boolean, nullable=False, default=True)

    user = orm.relation("User")
    manufacturer = orm.relation("Manufacturer")

    def __repr__(self):
        return f"Товар '{self.name}' (ID - {self.id})"
