import sqlalchemy as db
from .db_session import SqlAlchemyBase
from sqlalchemy import orm

from datetime import datetime


class Book(SqlAlchemyBase):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    status = db.Column(db.Integer, nullable=False)
    owner = db.Column(db.Integer, nullable=True)
    poster_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.now)
    toggle = db.Column(db.Boolean, nullable=False, default=True)

    user = orm.relation("User")
    product = orm.relation("Product")

    def __repr__(self):
        return f"Экземпляр книги '{self.product_id}' (ID - {self.id})"
