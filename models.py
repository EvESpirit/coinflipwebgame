import json
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    bet_amount = db.Column(db.Float, default=0.0)
    coin_toss_results_data = db.Column(db.String(), nullable=False, default="[]")

    @property
    def coin_toss_results(self):
        return json.loads(self.coin_toss_results_data)

    @coin_toss_results.setter
    def coin_toss_results(self, value):
        self.coin_toss_results_data = json.dumps(value)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
