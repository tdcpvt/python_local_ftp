import os
import json
import threading
import socket
import werkzeug
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

app = Flask(__name__)
app.secret_key = 'xp_sp2_retro_secret'

BASE_STORAGE = os.path.abspath("./ftp_root")
DB_FILE = os.path.abspath("./users_db.json")
os.makedirs(BASE_STORAGE, exist_ok=True)

# --- DATABASE ENGINE ---
def load_db():
    if not os.path.exists(DB_FILE):
        default_db = {
            "admin": {"password": "password123", "role": "admin", "can_delete": True},
            "alex": {"password": "pass", "role": "client", "can_delete": False},
            "jordan": {"password": "pass", "role": "client", "can_delete": True}
        }
        with open(DB_FILE, 'w') as f:
            json.dump(default_db, f, indent=4)
        return default_db
    with open(DB_FILE, 'r') as f:
        try:
            return json.load(f)
        except Exception:
            return {"admin": {"password": "password123", "role": "admin", "can_delete": True}}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

def setup_user_directories(username):
    user_root = os.path.join(BASE_STORAGE, username)
    os.makedirs(os.path.join(user_root, "Public"), exist_ok=True)
    os.makedirs(os.path.join(user_root, "Private"), exist_ok=True)

# Run initial framework validations
USERS_DB = load_db()
for user in USERS_DB:
    if USERS_DB[user]["role"] == "client":
        setup_user_directories(user)

# --- BACKGROUND FTP SERVER ---
def run_ftp_server():
    authorizer = DummyAuthorizer()
    current_db = load_db()
    for user, info in current_db.items():
        if info["role"] == "client":
            user_path = os.path.join(BASE_STORAGE, user)
            authorizer.add_user(user, info["password"], user_path, perm='elradfmwMT')
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.passive_ports = range(60000, 60050)
    server = FTPServer(('0.0.0.0', 28000), handler)
    server.serve_forever()

ftp_thread = threading.Thread(target=run_ftp_server, daemon=True)
ftp_thread.start()

# --- FLASK CORE WEB ROUTES ---
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('desktop'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    db = load_db()
    if username in db and db[username]['password'] == password:
        session['username'] = username
        session['role'] = db[username]['role']
        return redirect(url_for('desktop'))
    return "Invalid Credentials", 401

@app.route('/desktop')
def desktop():
    if 'username' not in session:
        return redirect(url_for('index'))
    db = load_db()
    clients = [u for u, info in db.items() if info['role'] == 'client']
    return render_template('desktop.html', username=session['username'], role=session.get('role'), clients=clients, full_db=db)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- WEB DATA TRANSMISSION ENDPOINTS ---
@app.route('/api/explore/<target_user>/<folder_type>')
def explore_folder(target_user, folder_type):
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    current_user = session['username']
    if folder_type == "Private" and current_user != target_user and session.get('role') != 'admin':
        return jsonify({"error": "Access Denied"}), 403

    target_path = os.path.join(BASE_STORAGE, target_user, folder_type)
    if not os.path.exists(target_path):
        return jsonify({"error": "Folder not found"}), 404

    db = load_db()
    user_permissions = db.get(current_user, {"can_delete": False})
    
    files = []
    for item in os.listdir(target_path):
        item_path = os.path.join(target_path, item)
        if not os.path.isdir(item_path):
            files.append({
                "name": item,
                "size": os.path.getsize(item_path),
                "allow_delete": user_permissions.get("can_delete", False) or session.get('role') == 'admin'
            })
    return jsonify({"files": files})

@app.route('/api/upload/<target_user>/<folder_type>', methods=['POST'])
def upload_file(target_user, folder_type):
    if 'username' not in session:
        return "Unauthorized", 401
    
    current_user = session['username']
    if folder_type == "Private" and current_user != target_user and session.get('role') != 'admin':
        return "Access Denied", 403

    if 'file' not in request.files:
        return "No file found", 400
    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    target_path = os.path.join(BASE_STORAGE, target_user, folder_type)
    filename = werkzeug.utils.secure_filename(file.filename)
    file.save(os.path.join(target_path, filename))
    return redirect(url_for('desktop'))

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    if 'username' not in session:
        return "Unauthorized", 401
    
    current_user = session['username']
    db = load_db()
    if session.get('role') != 'admin' and not db.get(current_user, {}).get("can_delete", False):
        return "Access Forbidden", 403
        
    target_user = request.form.get('target_user')
    folder_type = request.form.get('folder_type')
    filename = request.form.get('filename')
    
    file_path = os.path.abspath(os.path.join(BASE_STORAGE, target_user, folder_type, werkzeug.utils.secure_filename(filename)))
    if file_path.startswith(BASE_STORAGE) and os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"status": "deleted"})
    return "Invalid path", 400

# --- ACCOUNT ADMINISTRATION ---
@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    username = request.form.get('username').strip().lower()
    password = request.form.get('password')
    can_delete = request.form.get('can_delete') == 'true'
    
    db = load_db()
    db[username] = {"password": password, "role": "client", "can_delete": can_delete}
    save_db(db)
    setup_user_directories(username)
    return redirect(url_for('desktop'))

@app.route('/admin/delete_user/<username>', methods=['POST'])
def delete_user(username):
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    db = load_db()
    if username in db and db[username]['role'] != 'admin':
        del db[username]
        save_db(db)
        return jsonify({"status": "user_removed"})
    return "Invalid user", 400

@app.route('/api/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return "Unauthorized", 401
    current_user = session['username']
    new_password = request.form.get('new_password')
    
    db = load_db()
    if current_user in db:
        db[current_user]['password'] = new_password
        save_db(db)
        return jsonify({"status": "success"})
    return "Error updating record", 400

@app.route('/api/get_local_ip')
def get_local_ip_route():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return jsonify({"ip": ip})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
