import os
from flask import flash, redirect, url_for, render_template, request, Flask, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User  # Update this line
import secrets
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager
from waitress import serve
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


app.secret_key = '8weq789weq78qwe4fg4fg564jfj854ukl'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///coin_flip_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

secretsGenerator = secrets.SystemRandom()

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_coin_toss_results_and_balance_graph(user_id):
    user = User.query.get(user_id)
    if user is None:
        return []

    coin_toss_results = user.coin_toss_results
    balance_graph_data = [{'x': i, 'y': result['balance']} for i, result in enumerate(user.coin_toss_results)]

    return coin_toss_results, balance_graph_data


def read_balance(file_name):
    if os.path.exists(file_name):
        with open(file_name, 'r') as file:
            try:
                balance = float(file.readline().strip())
            except ValueError:
                balance = 1.0
    else:
        balance = 1.0
    return round(balance, 2)


def write_balance(file_name, balance):
    with open(file_name, 'w') as file:
        file.write(str(round(balance, 2)))


def update_user_coin_toss_results(user, coin_result, bet_amount, balance):
    user_coin_toss_results = user.coin_toss_results
    user_coin_toss_results.append(
        {'coin_result': coin_result, 'bet_amount': bet_amount, 'balance': balance})
    user.coin_toss_results = user_coin_toss_results[-20:]  # Store only the last 20 results
    db.session.commit()


def coin_flip(balance, bet_amount):
    flip = secretsGenerator.randint(0, 1)

    winstate = balance + (bet_amount * 0.5)
    lossstate = balance - (bet_amount * 0.5)
    if flip == 1:
        new_balance = winstate
        coin_result = 'heads'
    else:
        new_balance = lossstate
        coin_result = 'tails'

    if new_balance < 0.01:
        return 0
    else:
        session['coin_result'] = coin_result
        return round(new_balance, 4)


@app.route('/', methods=['GET', 'POST'])
@login_required
def play_game():
    if 'balance' not in session:
        session['balance'] = 1.0

    balance = current_user.balance

    if 'balance_history' not in session:
        session['balance_history'] = [balance]

    if request.method == 'GET':
        session['coin_result'] = None

    coin_result = session.get('coin_result')
    bet_amount = session.get('bet_amount', 0)
    update_user_coin_toss_results(current_user, coin_result, bet_amount, balance)

    if request.method == 'POST':
        choice = request.form['action']

        if choice == 'flip':
            bet_amount = float(request.form['bet_amount'])
            session['bet_amount'] = bet_amount
            if bet_amount > balance:
                flash("Your bet amount exceeds your current balance. Please choose a smaller bet.", "message")
                return redirect(url_for('render_game'))
            elif bet_amount <= 0:
                flash("Your bet amount needs to be greater than zero.", "message")
                return redirect(url_for('render_game'))
            else:
                balance = coin_flip(balance, bet_amount)
                session['balance'] = balance

                if balance == 0:
                    return redirect(url_for('game_over'))

        elif choice == 'all_in':
            bet_amount = balance
            balance = coin_flip(balance, bet_amount)
            session['balance'] = balance

            if balance == 0:
                return redirect(url_for('game_over'))

        elif choice == 'quit':
            session.pop('balance_history', None)
            return redirect(url_for('game_over'))

        # Update balance_history after processing coin flip
        session['balance_history'].append(balance)
        current_user.balance = balance
        db.session.commit()

        return redirect(url_for('render_game'))

    return render_template('index.html', balance=balance, coin_result=session['coin_result'],
                           balance_history=session['balance_history'], bet_amount=session.get('bet_amount', 0))


@app.route('/render_game')
def render_game():
    balance = session['balance']
    return render_template('index.html', balance=balance, coin_result=session['coin_result'],
                           balance_history=session['balance_history'], bet_amount=session.get('bet_amount', 0))


@app.route('/game_over', methods=['GET'])
@login_required
def game_over():
    balance = session.pop('balance', 0)
    session.pop('balance_history', None)

    # Reset the user balance back to 1 dollar
    current_user.balance = 1.0
    db.session.commit()

    return render_template('game_over.html', balance=balance)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('play_game'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter_by(username=username).first()
        if existing_user is None:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash("Registration successful. Please log in.")
            return redirect(url_for('login'))
        else:
            flash("User already exists. Please choose a different username.")

    return render_template('register.html')


@app.route('/account_history', methods=['GET'])
@login_required
def account_history():
    coin_toss_results, balance_graph_data = get_coin_toss_results_and_balance_graph(current_user.id)
    return render_template('account_history.html', coin_toss_results=coin_toss_results,
                           balance_graph_data=json.dumps(balance_graph_data), enumerate=enumerate)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('play_game'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user is not None and user.check_password(password):
            login_user(user)
            flash("Login successful.")
            return redirect(url_for('play_game'))
        else:
            flash("Invalid username or password.")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('login'))


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=80)
    serve(app, host='0.0.0.0', port=80)
