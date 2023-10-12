import sqlalchemy as db
from .db_session import SqlAlchemyBase
from sqlalchemy import orm

from datetime import datetime


class Order(SqlAlchemyBase):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False, index=True)
    poster_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    poster_name = db.Column(db.String, nullable=False)
    products_list = db.Column(db.String, nullable=False)
    address = db.Column(db.String, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    products_price = db.Column(db.String, nullable=False)
    books = db.Column(db.String, nullable=False)
    commentary = db.Column(db.String, nullable=True)
    status = db.Column(db.Integer, nullable=False, default=0)
    creation_date = db.Column(db.DateTime, default=datetime.now)

    user = orm.relation("User")

    def __repr__(self):
        return f"Заказ №{self.id} от пользователя {self.poster_name} (ID - {self.poster_id})"