import datetime as dt
import sqlalchemy as sa

from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref

from common.extensions.database import db

class Plot(db.Model):
    __tablename__ = "plots"

    plot_id = sa.Column(sa.String(length=8), primary_key=True)
    hostname = sa.Column(sa.String(length=255))
    dir = sa.Column(sa.String(length=255))
    file = sa.Column(sa.String(length=255))
    size = sa.Column(sa.Integer)
    created_at = sa.Column(sa.String(length=64))
    updated_at = sa.Column(sa.DateTime(), onupdate=func.now())

    