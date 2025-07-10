from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with your actual secret key

# Database configuration
db_config = {
    'user': 'root',
    'password': 'Neeru705',
    'host': 'localhost',
    'database': 'banking'
}

def get_db_connection():
    try:
        conn = pymysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

# Helper functions
def get_user_by_username(username):
    conn = get_db_connection()
    if not conn:
        return None
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    if not conn:
        return None
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

def update_user(username, email=None, password=None):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            if password:
                hashed_pw = generate_password_hash(password)
                cursor.execute("UPDATE users SET password = %s WHERE username = %s",
                               (hashed_pw, username))
        conn.commit()
    except Exception as e:
        print(f"Error updating user: {e}")
        conn.rollback()
        conn.close()
        return False
    conn.close()
    return True

def delete_user(username):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if user:
                user_id = user['id']
                cursor.execute("DELETE FROM transactions WHERE sender_id = %s OR receiver_id = %s", (user_id, user_id))
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting user: {e}")
        conn.rollback()
        conn.close()
        return False
    conn.close()
    return True

def get_transactions(user_id):
    conn = get_db_connection()
    if not conn:
        return []
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT t.id, t.sender_id, t.receiver_id, t.amount, t.timestamp,
                   u1.username AS sender_username,
                   u2.username AS receiver_username
            FROM transactions t
            JOIN users u1 ON t.sender_id = u1.id
            JOIN users u2 ON t.receiver_id = u2.id
            WHERE t.sender_id = %s OR t.receiver_id = %s
            ORDER BY t.timestamp DESC
        """, (user_id, user_id))
        txns = cursor.fetchall()
    conn.close()
    return txns

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        balance = request.form.get('balance')

        if not username or not password or not balance:
            flash("All fields are required!", "warning")
            return redirect(url_for("register"))

        conn = get_db_connection()
        if not conn:
            flash("Database connection failed.", "danger")
            return redirect(url_for("register"))

        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password, balance) VALUES (%s, %s, %s)",
                (username, generate_password_hash(password), balance)
            )
            conn.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error during registration: {e}", "danger")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please enter both username and password', 'warning')
            return redirect(url_for('login'))

        user = get_user_by_username(username)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard', 'warning')
        return redirect(url_for('login'))

    user = get_user_by_id(session['user_id'])
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('login'))

    return render_template('dashboard.html', username=user['username'], balance=user['balance'])

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash('User not found.')
        return redirect(url_for('login'))

    return render_template('profile.html', username=user['username'], balance=user['balance'])

@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    txns = get_transactions(session['user_id'])
    return render_template('transactions.html', transactions=txns)

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if delete_user(session['username']):
        session.clear()
        flash('Account deleted successfully.', 'info')
        return redirect(url_for('register'))
    else:
        flash('Failed to delete account.', 'danger')
        return redirect(url_for('profile'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        from_user_id = session['user_id']
        to_username = request.form.get('to_user')
        amount = request.form.get('amount')

        if not to_username or not amount:
            flash('Please enter recipient username and amount.', 'warning')
            return redirect(url_for('transfer'))

        try:
            amount = float(amount)
            if amount <= 0:
                flash('Amount must be positive.', 'warning')
                return redirect(url_for('transfer'))
        except ValueError:
            flash('Invalid amount entered.', 'warning')
            return redirect(url_for('transfer'))

        sender = get_user_by_id(from_user_id)
        receiver = get_user_by_username(to_username)

        if not receiver:
            flash('Recipient user does not exist.', 'danger')
            return redirect(url_for('transfer'))

        if sender['balance'] < amount:
            flash('Insufficient balance.', 'danger')
            return redirect(url_for('transfer'))

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('transfer'))

        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, from_user_id))
                cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, receiver['id']))
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("INSERT INTO transactions (sender_id, receiver_id, amount, timestamp) VALUES (%s, %s, %s, %s)",
                               (from_user_id, receiver['id'], amount, now))
            conn.commit()
            flash('Transfer successful!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Transfer failed: {e}', 'danger')
        finally:
            conn.close()

        return redirect(url_for('dashboard'))

    return render_template('transfer.html')

if __name__ == '__main__':
    app.run(debug=True)
