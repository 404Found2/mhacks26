import json
import os
import sqlite3
from flask import Flask, jsonify, request, session as flask_session
from flask_cors import CORS
from datetime import datetime
import uuid
from functools import wraps
from openrouter_chat import (
    OpenRouterError,
    complete_strategy_turn,
    lift_inline_chips,
    normalize_todos,
    propose_strategy_todos,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OWNED_TABLES = ('personas', 'strategy', 'products', 'todos', 'messages', 'settings')

def load_local_env():
    """Load backend/.env without overriding variables already set in the shell."""
    path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(path):
        return
    with open(path, 'r') as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_local_env()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DATABASE'] = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'northstar.db'))
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

CORS(app, supports_credentials=True)

def get_db():
    """Get database connection"""
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db

def init_db():
    """Initialize the database from schemas.sql"""
    db = get_db()
    with open(os.path.join(BASE_DIR, 'schemas.sql'), 'r') as f:
        db.executescript(f.read())
    db.commit()
    db.close()

def ensure_messages_table():
    """Add the messages table to databases created before chat history was stored."""
    db = get_db()
    db.execute(
        '''CREATE TABLE IF NOT EXISTS messages (
            sessionid VARCHAR(36),
            userid INTEGER,
            role VARCHAR(20) NOT NULL,
            content VARCHAR(4000) NOT NULL,
            chips TEXT,
            statement VARCHAR(1000),
            kind VARCHAR(20),
            created DATETIME DEFAULT current_timestamp,
            FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
            FOREIGN KEY (userid) REFERENCES users(userid),
            CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
        )'''
    )
    columns = {row[1] for row in db.execute('PRAGMA table_info(messages)')}
    for name, declaration in (
        ('chips', 'TEXT'),
        ('statement', 'VARCHAR(1000)'),
        ('kind', 'VARCHAR(20)'),
    ):
        if name not in columns:
            db.execute(f'ALTER TABLE messages ADD COLUMN {name} {declaration}')
    db.commit()
    db.close()

ensure_messages_table()

def ensure_settings_table():
    """Remember when a dashboard task list was created or cleared."""
    db = get_db()
    db.execute(
        '''CREATE TABLE IF NOT EXISTS settings (
            sessionid VARCHAR(36),
            userid INTEGER,
            todos_initialized INTEGER NOT NULL DEFAULT 0,
            created DATETIME DEFAULT current_timestamp,
            FOREIGN KEY (sessionid) REFERENCES sessions(sessionid) ON DELETE CASCADE,
            FOREIGN KEY (userid) REFERENCES users(userid),
            CONSTRAINT chk_valid CHECK ((sessionid IS NOT NULL AND userid IS NULL) OR (sessionid IS NULL AND userid IS NOT NULL))
        )'''
    )
    db.commit()
    db.close()

ensure_settings_table()

def get_or_create_session():
    """Get existing session or create new anonymous session"""
    db = get_db()
    try:
        session_id = flask_session.get('session_id')
        if session_id:
            row = db.execute(
                'SELECT sessionid FROM sessions WHERE sessionid = ?',
                (session_id,)
            ).fetchone()
        else:
            row = None

        if row is None:
            session_id = str(uuid.uuid4())
            db.execute(
                'INSERT INTO sessions (sessionid, userid) VALUES (?, ?)',
                (session_id, None)
            )
            db.commit()
            flask_session['session_id'] = session_id
        return session_id
    finally:
        db.close()

def claim_session_for_user(user_id):
    """Attach the current anonymous session, and its records, to a user."""
    session_id = get_or_create_session()
    db = get_db()
    try:
        db.execute(
            'UPDATE sessions SET userid = ? WHERE sessionid = ?',
            (user_id, session_id)
        )
        for table in OWNED_TABLES:
            db.execute(
                f'UPDATE {table} SET userid = ?, sessionid = NULL WHERE sessionid = ?',
                (user_id, session_id)
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    flask_session['user_id'] = user_id
    return session_id

def require_session(f):
    """Decorator to ensure session exists"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = get_or_create_session()
        return f(*args, **kwargs)
    return decorated_function

# Auth Routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user and attach the anonymous session."""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not username or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            (username, email, password)
        )
        db.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 409
    finally:
        db.close()

    session_id = claim_session_for_user(user_id)
    return jsonify({
        'message': 'User registered successfully',
        'user_id': user_id,
        'username': username,
        'session_id': session_id,
        'is_authenticated': True
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user and convert the anonymous session to their userid."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Missing email or password'}), 400

    db = get_db()
    user = db.execute(
        'SELECT userid, username, email FROM users WHERE email = ? AND password = ?',
        (email, password)
    ).fetchone()
    db.close()

    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    session_id = claim_session_for_user(user['userid'])
    return jsonify({
        'message': 'Logged in successfully',
        'user_id': user['userid'],
        'username': user['username'],
        'session_id': session_id,
        'is_authenticated': True
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user and start a fresh anonymous session. Account tasks stay in todos."""
    flask_session.clear()
    session_id = get_or_create_session()
    return jsonify({
        'message': 'Logged out successfully',
        'session_id': session_id,
        'user_id': None,
        'username': None,
        'is_authenticated': False
    }), 200

# Session Routes
@app.route('/api/session', methods=['GET'])
@require_session
def get_session():
    """Get current session info"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    username = None
    if user_id is not None:
        db = get_db()
        user = db.execute(
            'SELECT username FROM users WHERE userid = ?',
            (user_id,)
        ).fetchone()
        db.close()
        username = user['username'] if user else None
        if username is None:
            flask_session.pop('user_id', None)
            user_id = None
    return jsonify({
        'session_id': session_id,
        'user_id': user_id,
        'username': username,
        'is_authenticated': user_id is not None
    }), 200

# Personas Routes
@app.route('/api/personas', methods=['GET'])
@require_session
def get_personas():
    """Get all personas for current session/user"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    
    db = get_db()
    personas = db.execute(
        'SELECT * FROM personas WHERE (sessionid = ? OR userid = ?) ORDER BY created DESC',
        (session_id if not user_id else None, user_id)
    ).fetchall()
    db.close()
    
    return jsonify([dict(p) for p in personas]), 200

@app.route('/api/personas', methods=['POST'])
@require_session
def create_persona():
    """Create a new persona"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    demographics = data.get('demographics')
    habits = data.get('habits')
    pains = data.get('pains')
    
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO personas (sessionid, userid, demographics, habits, pains) VALUES (?, ?, ?, ?, ?)',
            (session_id if not user_id else None, user_id, demographics, habits, pains)
        )
        db.commit()
        persona_id = cursor.lastrowid
        db.close()
        return jsonify({
            'message': 'Persona created successfully',
            'id': persona_id
        }), 201
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

@app.route('/api/personas/<int:persona_id>', methods=['PUT'])
@require_session
def update_persona(persona_id):
    """Update a persona"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    db = get_db()
    try:
        db.execute(
            'UPDATE personas SET demographics = ?, habits = ?, pains = ? WHERE rowid = ? AND (sessionid = ? OR userid = ?)',
            (data.get('demographics'), data.get('habits'), data.get('pains'), persona_id, session_id if not user_id else None, user_id)
        )
        db.commit()
        db.close()
        return jsonify({'message': 'Persona updated successfully'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

# Strategy Routes
@app.route('/api/strategy', methods=['GET'])
@require_session
def get_strategy():
    """Get all strategies for current session/user"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    
    db = get_db()
    strategies = db.execute(
        'SELECT * FROM strategy WHERE (sessionid = ? OR userid = ?) ORDER BY created DESC',
        (session_id if not user_id else None, user_id)
    ).fetchall()
    db.close()
    
    return jsonify([dict(s) for s in strategies]), 200

@app.route('/api/strategy', methods=['POST'])
@require_session
def create_strategy():
    """Create a new strategy"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    statement = data.get('statement')
    steps = data.get('steps')
    
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO strategy (sessionid, userid, statement, steps) VALUES (?, ?, ?, ?)',
            (session_id if not user_id else None, user_id, statement, steps)
        )
        db.commit()
        strategy_id = cursor.lastrowid
        db.close()
        return jsonify({
            'message': 'Strategy created successfully',
            'id': strategy_id
        }), 201
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

@app.route('/api/strategy/<int:strategy_id>', methods=['PUT'])
@require_session
def update_strategy(strategy_id):
    """Update a strategy"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    db = get_db()
    try:
        db.execute(
            'UPDATE strategy SET statement = ?, steps = ? WHERE rowid = ? AND (sessionid = ? OR userid = ?)',
            (data.get('statement'), data.get('steps'), strategy_id, session_id if not user_id else None, user_id)
        )
        db.commit()
        db.close()
        return jsonify({'message': 'Strategy updated successfully'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

# Products Routes
@app.route('/api/products', methods=['GET'])
@require_session
def get_products():
    """Get all products for current session/user"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    
    db = get_db()
    products = db.execute(
        'SELECT * FROM products WHERE (sessionid = ? OR userid = ?) ORDER BY created DESC',
        (session_id if not user_id else None, user_id)
    ).fetchall()
    db.close()
    
    return jsonify([dict(p) for p in products]), 200

@app.route('/api/products', methods=['POST'])
@require_session
def create_product():
    """Create a new product"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    name = data.get('name')
    des = data.get('des')
    price = data.get('price')
    margin = data.get('margin')
    
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO products (sessionid, userid, name, des, price, margin) VALUES (?, ?, ?, ?, ?, ?)',
            (session_id if not user_id else None, user_id, name, des, price, margin)
        )
        db.commit()
        product_id = cursor.lastrowid
        db.close()
        return jsonify({
            'message': 'Product created successfully',
            'id': product_id
        }), 201
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

@app.route('/api/products/<int:product_id>', methods=['PUT'])
@require_session
def update_product(product_id):
    """Update a product"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    db = get_db()
    try:
        db.execute(
            'UPDATE products SET name = ?, des = ?, price = ?, margin = ? WHERE rowid = ? AND (sessionid = ? OR userid = ?)',
            (data.get('name'), data.get('des'), data.get('price'), data.get('margin'), product_id, session_id if not user_id else None, user_id)
        )
        db.commit()
        db.close()
        return jsonify({'message': 'Product updated successfully'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@require_session
def delete_product(product_id):
    """Delete a product"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    
    db = get_db()
    try:
        db.execute(
            'DELETE FROM products WHERE rowid = ? AND (sessionid = ? OR userid = ?)',
            (product_id, session_id if not user_id else None, user_id)
        )
        db.commit()
        db.close()
        return jsonify({'message': 'Product deleted successfully'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

def todo_owner(session_id, user_id):
    return (session_id if not user_id else None, user_id)

def fetch_todos(db, owner):
    return db.execute(
        '''SELECT rowid AS id, name, des, status, created
           FROM todos
           WHERE (sessionid = ? OR userid = ?)
           ORDER BY rowid ASC''',
        owner
    ).fetchall()

def settings_for(db, owner):
    return db.execute(
        '''SELECT rowid AS id, todos_initialized
           FROM settings
           WHERE (sessionid = ? OR userid = ?)
           ORDER BY rowid DESC
           LIMIT 1''',
        owner
    ).fetchone()

def mark_todos_initialized(db, owner):
    row = settings_for(db, owner)
    if row is None:
        db.execute(
            'INSERT INTO settings (sessionid, userid, todos_initialized) VALUES (?, ?, 1)',
            (owner[0], owner[1])
        )
    elif not row['todos_initialized']:
        db.execute(
            'UPDATE settings SET todos_initialized = 1 WHERE rowid = ?',
            (row['id'],)
        )

# Todos Routes
@app.route('/api/todos', methods=['GET'])
@require_session
def get_todos():
    """Get focus tasks for the current session or user. New visitors start with none."""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    owner = todo_owner(session_id, user_id)

    db = get_db()
    try:
        todos = fetch_todos(db, owner)
        return jsonify([dict(todo) for todo in todos]), 200
    finally:
        db.close()

@app.route('/api/todos', methods=['DELETE'])
@require_session
def clear_todos():
    """Remove every focus task for the current session or user."""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    owner = todo_owner(session_id, user_id)
    db = get_db()
    try:
        db.execute(
            'DELETE FROM todos WHERE (sessionid = ? OR userid = ?)',
            owner
        )
        mark_todos_initialized(db, owner)
        db.commit()
        return jsonify([]), 200
    finally:
        db.close()

@app.route('/api/todos', methods=['POST'])
@require_session
def create_todo():
    """Create a new todo"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    name = data.get('name')
    des = data.get('des')
    status = data.get('status', 'pending')
    
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO todos (sessionid, userid, name, des, status) VALUES (?, ?, ?, ?, ?)',
            (session_id if not user_id else None, user_id, name, des, status)
        )
        db.commit()
        todo_id = cursor.lastrowid
        db.close()
        return jsonify({
            'message': 'Todo created successfully',
            'id': todo_id
        }), 201
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
@require_session
def update_todo(todo_id):
    """Update a todo. A checkbox sends only status."""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    data = request.get_json(silent=True) or {}
    owner = todo_owner(session_id, user_id)

    db = get_db()
    try:
        row = db.execute(
            'SELECT name, des, status FROM todos WHERE rowid = ? AND (sessionid = ? OR userid = ?)',
            (todo_id, *owner)
        ).fetchone()
        if row is None:
            return jsonify({'error': 'Todo not found'}), 404

        status = data.get('status', row['status'])
        if status not in ('pending', 'complete'):
            return jsonify({'error': 'Status must be pending or complete'}), 400

        name = data.get('name', row['name'])
        des = data.get('des', row['des'])
        db.execute(
            'UPDATE todos SET name = ?, des = ?, status = ? WHERE rowid = ? AND (sessionid = ? OR userid = ?)',
            (name, des, status, todo_id, *owner)
        )
        db.commit()
        return jsonify({
            'id': todo_id,
            'name': name,
            'des': des,
            'status': status,
        }), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@require_session
def delete_todo(todo_id):
    """Delete a todo"""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    
    db = get_db()
    try:
        db.execute(
            'DELETE FROM todos WHERE rowid = ? AND (sessionid = ? OR userid = ?)',
            (todo_id, session_id if not user_id else None, user_id)
        )
        db.commit()
        db.close()
        return jsonify({'message': 'Todo deleted successfully'}), 200
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

# Health check
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

def latest_owned(db, table, owner):
    return db.execute(
        f'SELECT rowid AS id, * FROM {table} WHERE (sessionid = ? OR userid = ?) ORDER BY created DESC LIMIT 1',
        owner
    ).fetchone()

def saved_strategy_context(owner):
    db = get_db()
    try:
        persona = latest_owned(db, 'personas', owner)
        strategy = latest_owned(db, 'strategy', owner)
        return (
            {
                'demographics': persona['demographics'] if persona else '',
                'habits': persona['habits'] if persona else '',
                'pains': persona['pains'] if persona else '',
            },
            strategy['statement'] if strategy and strategy['statement'] else '',
        )
    finally:
        db.close()

def persist_persona(owner, persona):
    demographics = persona.get('demographics') or ''
    habits = persona.get('habits') or ''
    pains = persona.get('pains') or ''
    if not any((demographics, habits, pains)):
        return None

    db = get_db()
    try:
        row = latest_owned(db, 'personas', owner)
        if row is None:
            cursor = db.execute(
                'INSERT INTO personas (sessionid, userid, demographics, habits, pains) VALUES (?, ?, ?, ?, ?)',
                (owner[0], owner[1], demographics, habits, pains)
            )
            persona_id = cursor.lastrowid
        else:
            persona_id = row['id']
            db.execute(
                'UPDATE personas SET demographics = ?, habits = ?, pains = ? WHERE rowid = ?',
                (
                    demographics or row['demographics'],
                    habits or row['habits'],
                    pains or row['pains'],
                    persona_id,
                )
            )
        db.commit()
        saved = db.execute(
            'SELECT rowid AS id, demographics, habits, pains FROM personas WHERE rowid = ?',
            (persona_id,)
        ).fetchone()
        return dict(saved)
    finally:
        db.close()

def persist_strategy(owner, statement, steps):
    if not statement:
        return None

    db = get_db()
    try:
        row = latest_owned(db, 'strategy', owner)
        if row is None:
            cursor = db.execute(
                'INSERT INTO strategy (sessionid, userid, statement, steps) VALUES (?, ?, ?, ?)',
                (owner[0], owner[1], statement, steps)
            )
            strategy_id = cursor.lastrowid
        else:
            strategy_id = row['id']
            db.execute(
                'UPDATE strategy SET statement = ?, steps = ? WHERE rowid = ?',
                (statement, steps or row['steps'], strategy_id)
            )
        db.commit()
        saved = db.execute(
            'SELECT rowid AS id, statement, steps FROM strategy WHERE rowid = ?',
            (strategy_id,)
        ).fetchone()
        return dict(saved)
    finally:
        db.close()

PROFILE_FIELDS = ('demographics', 'habits', 'pains')

def choice_text(message):
    return ' '.join(message.lower().replace('?', ' ').replace('!', ' ').replace('.', ' ').split())

def wants_to_keep(message):
    choice = choice_text(message)
    return choice in {
        'keep', 'keep it', 'keep this profile', 'yes', 'yes keep it',
    } or choice.startswith('keep this')

def wants_to_save_statement(message):
    choice = choice_text(message)
    return choice in {'save', 'save it', 'save to dashboard', 'save to the dashboard', 'yes save it'}

def wants_to_add_todos(message):
    choice = choice_text(message)
    return choice in {
        'add these tasks', 'add these', 'add them', 'add these to the dashboard',
        'yes add them', 'approve', 'approve them',
    } or choice.startswith('add these')

def asks_for_todos(message):
    choice = choice_text(message)
    return any(phrase in choice for phrase in (
        'todo', 'task list', 'tasks', 'what should i do', 'next steps',
    ))

def todo_key(todos):
    return '|'.join(todo['name'].strip().lower() for todo in todos if todo.get('name'))

def todo_offer_text(todos):
    lines = ['Here are the next tasks for this strategy:']
    for index, todo in enumerate(todos, 1):
        if todo.get('des'):
            lines.append(f"{index}. {todo['name']} — {todo['des']}")
        else:
            lines.append(f"{index}. {todo['name']}")
    lines.append('Add these to your dashboard?')
    return '\n'.join(lines)

def should_show_todos(todos):
    key = todo_key(todos)
    if not key:
        return False
    if key == (flask_session.get('saved_todo_key') or ''):
        return False
    if key == (flask_session.get('skipped_todo_key') or ''):
        return False
    return True

def remember_todo_offer(todos):
    flask_session['todo_draft'] = todos
    flask_session['awaiting_todo_confirm'] = True
    flask_session['todos_prompted'] = True
    flask_session.modified = True

def persist_approved_todos(owner, todos):
    """Add approved tasks that are not already on this dashboard."""
    db = get_db()
    try:
        existing = {
            (row['name'] or '').strip().lower()
            for row in fetch_todos(db, owner)
        }
        added = []
        for todo in todos:
            name = (todo.get('name') or '').strip()
            if not name or name.lower() in existing:
                continue
            db.execute(
                'INSERT INTO todos (sessionid, userid, name, des, status) VALUES (?, ?, ?, ?, ?)',
                (owner[0], owner[1], name[:255], (todo.get('des') or '')[:1000], 'pending')
            )
            existing.add(name.lower())
            added.append({'name': name, 'des': todo.get('des') or ''})
        db.commit()
        return added
    finally:
        db.close()

def wants_to_skip_statement(message):
    choice = choice_text(message)
    return choice in {'not now', 'no', 'skip', 'later', 'not yet'}

def statement_prompt():
    return 'Save this strategy statement to the dashboard?'

def wants_to_revise(message):
    choice = choice_text(message)
    return choice in {'revise', 'revise it', 'change it', 'no', 'not yet'} or choice.startswith('revise')

def profile_is_complete(draft):
    return all((draft.get(field) or '').strip() for field in PROFILE_FIELDS)

def profile_summary(draft):
    lines = [
        'Here is the customer profile:',
        f"Demographic: {draft.get('demographics')}",
        f"Challenges: {draft.get('pains')}",
        f"Behaviors & habits: {draft.get('habits')}",
    ]
    lines.append('Keep this profile? It will show on your home page.')
    return '\n'.join(lines)

def insert_message(db, owner, role, content, chips=None, statement='', kind=None):
    text = (content or '').strip()
    if not text or role not in ('user', 'assistant'):
        return
    chip_values = [chip.strip() for chip in (chips or []) if isinstance(chip, str) and chip.strip()]
    db.execute(
        '''INSERT INTO messages (sessionid, userid, role, content, chips, statement, kind)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (
            owner[0],
            owner[1],
            role,
            text,
            json.dumps(chip_values) if chip_values else None,
            (statement or '').strip() or None,
            kind if kind == 'accent' else None,
        )
    )

def history_item(item):
    if not isinstance(item, dict):
        return None
    role = item.get('role')
    content = (item.get('content') or item.get('text') or '').strip()
    if role not in ('user', 'assistant') or not content:
        return None
    chips = item.get('chips') if isinstance(item.get('chips'), list) else []
    statement = item.get('statement') or ''
    kind = item.get('kind')
    return role, content, chips, statement, kind

def is_subsequence(stored, incoming):
    index = 0
    for item in incoming:
        if index < len(stored) and stored[index] == item:
            index += 1
    return index == len(stored)

def persist_prior_messages(owner, history, user_message):
    """Write earlier thread turns that were never stored, then the new user line."""
    items = []
    for item in history or []:
        normalized = history_item(item)
        if normalized:
            items.append(normalized)
    incoming = [(role, content) for role, content, _chips, _statement, _kind in items]
    user_text = (user_message or '').strip()

    db = get_db()
    try:
        stored = [
            (row['role'], row['content'])
            for row in db.execute(
                '''SELECT role, content FROM messages
                   WHERE (sessionid = ? OR userid = ?)
                   ORDER BY rowid ASC''',
                owner
            )
        ]
        if len(incoming) > len(stored) and is_subsequence(stored, incoming):
            db.execute(
                'DELETE FROM messages WHERE (sessionid = ? OR userid = ?)',
                owner
            )
            for role, content, chips, statement, kind in items:
                insert_message(db, owner, role, content, chips, statement, kind)
        if user_text:
            insert_message(db, owner, 'user', user_text)
        db.commit()
    finally:
        db.close()

def save_assistant_turn(owner, message, chips, accent, statement):
    db = get_db()
    try:
        if (accent or '').strip():
            insert_message(db, owner, 'assistant', accent, kind='accent')
        insert_message(db, owner, 'assistant', message, chips, statement)
        db.commit()
    finally:
        db.close()

def finish_chat(owner, message, chips, accent, statement, persona, strategy, saved=False):
    save_assistant_turn(owner, message, chips, accent, statement)
    return chat_payload(message, chips, accent, statement, persona, strategy, saved), 200

def statement_needs_save(draft):
    statement = (draft.get('statement') or '').strip()
    if not statement:
        return False
    if statement == (flask_session.get('saved_statement') or ''):
        return False
    if statement == (flask_session.get('skipped_statement') or ''):
        return False
    return True

def chat_payload(message, chips, accent, statement, persona, strategy, saved=False):
    return jsonify({
        'message': message,
        'chips': chips,
        'accent': accent,
        'statement': statement or '',
        'persona': persona,
        'strategy': strategy,
        'saved': saved,
    })

CHAT_SESSION_KEYS = (
    'profile_draft',
    'awaiting_profile_confirm',
    'awaiting_statement_confirm',
    'awaiting_todo_confirm',
    'profile_revision',
    'saved_statement',
    'skipped_statement',
    'todo_draft',
    'saved_todo_key',
    'skipped_todo_key',
    'todos_prompted',
)

def clear_chat_session():
    for key in CHAT_SESSION_KEYS:
        flask_session.pop(key, None)
    flask_session.modified = True

@app.route('/api/messages', methods=['DELETE'])
@require_session
def clear_messages():
    """Delete the saved chat and the in-progress interview for this owner."""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    owner = todo_owner(session_id, user_id)
    db = get_db()
    try:
        db.execute(
            'DELETE FROM messages WHERE (sessionid = ? OR userid = ?)',
            owner
        )
        db.commit()
    finally:
        db.close()
    clear_chat_session()
    return jsonify([]), 200

@app.route('/api/messages', methods=['GET'])
@require_session
def get_messages():
    """Return the saved chat thread for the current session or user."""
    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    owner = todo_owner(session_id, user_id)
    db = get_db()
    try:
        rows = db.execute(
            '''SELECT role, content, chips, statement, kind, created
               FROM messages
               WHERE (sessionid = ? OR userid = ?)
               ORDER BY rowid ASC''',
            owner
        ).fetchall()
        messages = []
        for row in rows:
            content, chips = lift_inline_chips(row['content'], row['chips'])
            messages.append({
                'role': row['role'],
                'content': content,
                'chips': chips,
                'statement': row['statement'] or '',
                'kind': row['kind'] or '',
                'created': row['created'],
            })
        return jsonify(messages), 200
    finally:
        db.close()

@app.route('/api/chat', methods=['POST'])
@require_session
def chat():
    """Ask OpenRouter for the next persona turn, then save only if the user keeps it."""
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Missing message'}), 400

    session_id = get_or_create_session()
    user_id = flask_session.get('user_id')
    owner = todo_owner(session_id, user_id)
    persist_prior_messages(owner, data.get('history') or [], message)
    draft = dict(flask_session.get('profile_draft') or {})
    awaiting = bool(flask_session.get('awaiting_profile_confirm'))
    awaiting_statement = bool(flask_session.get('awaiting_statement_confirm'))
    awaiting_todos = bool(flask_session.get('awaiting_todo_confirm'))
    saved_flag = bool(flask_session.get('profile_saved'))

    if awaiting_statement and wants_to_save_statement(message):
        statement = draft.get('statement') or ''
        strategy = persist_strategy(owner, statement, draft.get('steps') or '')
        flask_session['awaiting_statement_confirm'] = False
        flask_session['saved_statement'] = statement
        flask_session['skipped_statement'] = ''
        flask_session.modified = True
        persona, _saved_statement = saved_strategy_context(owner)
        try:
            proposed = propose_strategy_todos(
                statement,
                draft.get('steps') or '',
                persona,
            )
        except OpenRouterError:
            proposed = []
        if should_show_todos(proposed):
            remember_todo_offer(proposed)
            return finish_chat(
                owner,
                'Saved. This strategy statement is now on your dashboard.\n\n' + todo_offer_text(proposed),
                ['Add these tasks', 'Revise them'],
                'Strategy saved. Here are the tasks to execute it.',
                '',
                None,
                strategy,
                saved=True,
            )
        return finish_chat(
            owner,
            'Saved. This strategy statement is now on your dashboard.',
            [],
            'Saved to the dashboard.',
            '',
            None,
            strategy,
            saved=True,
        )

    if awaiting_statement and wants_to_skip_statement(message):
        flask_session['awaiting_statement_confirm'] = False
        flask_session['skipped_statement'] = draft.get('statement') or ''
        flask_session.modified = True

    if awaiting and wants_to_keep(message):
        persona = persist_persona(owner, draft)
        flask_session['awaiting_profile_confirm'] = False
        flask_session['profile_saved'] = True
        flask_session['profile_revision'] = False
        reply = 'Saved. This profile is now on your home page.'
        chips = []
        accent = 'Kept this customer profile.'
        offered_statement = ''
        if statement_needs_save(draft):
            flask_session['awaiting_statement_confirm'] = True
            reply = f'{reply}\n\n{statement_prompt()}'
            chips = ['Save to dashboard', 'Not now']
            accent = 'Profile saved. The strategy statement is ready for the dashboard.'
            offered_statement = draft.get('statement') or ''
        flask_session.modified = True
        return finish_chat(
            owner,
            reply,
            chips,
            accent,
            offered_statement,
            persona,
            None,
        )

    if awaiting_todos and wants_to_add_todos(message):
        added = persist_approved_todos(owner, normalize_todos(flask_session.get('todo_draft')))
        flask_session['awaiting_todo_confirm'] = False
        flask_session['saved_todo_key'] = todo_key(normalize_todos(flask_session.get('todo_draft')))
        flask_session['skipped_todo_key'] = ''
        flask_session.modified = True
        if added:
            reply = 'Added. These tasks are now on your dashboard.'
            accent = 'Tasks added to the dashboard.'
        else:
            reply = 'Those tasks are already on your dashboard.'
            accent = 'Nothing new to add.'
        return finish_chat(owner, reply, [], accent, '', None, None)

    if awaiting_todos and wants_to_skip_statement(message):
        flask_session['awaiting_todo_confirm'] = False
        flask_session['skipped_todo_key'] = todo_key(normalize_todos(flask_session.get('todo_draft')))
        flask_session.modified = True
        return finish_chat(
            owner,
            'Okay. I left the dashboard as it is.',
            [],
            'Tasks not added.',
            '',
            None,
            None,
        )

    db_persona, db_statement = saved_strategy_context(owner)
    developing_todos = awaiting_todos or (bool(db_statement) and asks_for_todos(message))
    if developing_todos:
        if wants_to_revise(message):
            feedback = 'Revise this list. Make the tasks more specific to the strategy.'
        else:
            feedback = message
        try:
            proposed = propose_strategy_todos(
                db_statement or draft.get('statement') or '',
                draft.get('steps') or '',
                db_persona,
                feedback=feedback,
                current=normalize_todos(flask_session.get('todo_draft')),
            )
        except OpenRouterError as exc:
            status = 503 if exc.status == 'config' else 502
            return jsonify({'error': str(exc)}), status
        if proposed and (awaiting_todos or should_show_todos(proposed)):
            remember_todo_offer(proposed)
            return finish_chat(
                owner,
                todo_offer_text(proposed),
                ['Add these tasks', 'Revise them'],
                'The task list is ready for your dashboard.',
                '',
                None,
                None,
            )
        if awaiting_todos:
            return finish_chat(
                owner,
                'I could not shape a new task list from that. Tell me what to change, or add the current tasks.',
                ['Add these tasks', 'Revise them'],
                '',
                '',
                None,
                None,
            )

    revising = bool(flask_session.get('profile_revision'))
    if awaiting and wants_to_revise(message):
        flask_session['awaiting_profile_confirm'] = False
        flask_session['profile_revision'] = True
        flask_session.modified = True
        revising = True

    db_persona, db_statement = saved_strategy_context(owner)

    try:
        turn = complete_strategy_turn(
            message,
            data.get('history') or [],
            db_persona,
            db_statement,
            draft,
        )
    except OpenRouterError as exc:
        status = 503 if exc.status == 'config' else 502
        return jsonify({'error': str(exc)}), status

    previous = {field: draft.get(field, '') for field in PROFILE_FIELDS}
    previous_statement = draft.get('statement') or ''
    for field in PROFILE_FIELDS:
        if turn['persona'].get(field):
            draft[field] = turn['persona'][field]
    if turn['statement']:
        draft['statement'] = turn['statement']
    if turn['steps']:
        draft['steps'] = turn['steps']
    changed = any(draft.get(field, '') != previous[field] for field in PROFILE_FIELDS)
    changed = changed or ((draft.get('statement') or '') != previous_statement)

    flask_session['profile_draft'] = draft
    reply = turn['reply']
    chips = turn['chips']
    accent = turn['accent']
    offered_statement = ''
    persona = None
    strategy = None
    saved = False

    if saved_flag and profile_is_complete(draft):
        persona = persist_persona(owner, draft)
    if profile_is_complete(draft) and not saved_flag and not (revising and not changed):
        flask_session['awaiting_profile_confirm'] = True
        flask_session['profile_revision'] = False
        reply = profile_summary(draft)
        chips = ['Keep this profile', 'Revise it']
        accent = accent or 'The customer profile is ready to keep.'
    elif statement_needs_save(draft):
        flask_session['awaiting_statement_confirm'] = True
        reply = statement_prompt()
        chips = ['Save to dashboard', 'Not now']
        accent = accent or 'The strategy statement is ready for the dashboard.'
        offered_statement = draft.get('statement') or ''
    elif (db_statement or flask_session.get('saved_statement')) and should_show_todos(turn.get('todos')):
        remember_todo_offer(turn['todos'])
        reply = todo_offer_text(turn['todos'])
        chips = ['Add these tasks', 'Revise them']
        accent = accent or 'The task list is ready for your dashboard.'

    flask_session.modified = True
    return finish_chat(owner, reply, chips, accent, offered_statement, persona, strategy, saved)

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    if not os.path.exists(app.config['DATABASE']):
        init_db()
    app.run(debug=True, port=5000)
