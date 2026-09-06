import os
import sys
import subprocess

VENV_DIR = os.path.abspath("./venv")

def bootstrap_venv():
    # Detect if we are already running inside our target virtual environment
    is_in_venv = sys.prefix != sys.base_prefix or 'VIRTUAL_ENV' in os.environ
    
    if not is_in_venv:
        print("[System] Termux environment detected. Checking virtual environment...")
        
        # 1. Create the venv if it doesn't exist
        if not os.path.exists(VENV_DIR):
            print("[System] Creating a clean Python virtual environment (venv)...")
            subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
            print("[System] Virtual environment created successfully.")
            
        # 2. Determine the path to the venv's python executable
        # Termux/Linux uses 'bin/python'; Windows uses 'Scripts/python.exe'
        venv_python = os.path.join(VENV_DIR, "bin", "python")
        if not os.path.exists(venv_python):
            venv_python = os.path.join(VENV_DIR, "Scripts", "python.exe")

        # 3. Check for requirements.txt and install them inside the venv
        req_file = os.path.abspath("./requirements.txt")
        if os.path.exists(req_file):
            print("[System] Installing/Verifying dependencies inside the venv...")
            subprocess.check_call([venv_python, "-m", "pip", "install", "-r", req_file, "--quiet"])
            # Ensure werkzeug is explicitly covered if it wasn't bundled
            subprocess.check_call([venv_python, "-m", "pip", "install", "werkzeug", "--quiet"])

        # 4. Relaunch this exact script using the venv's isolated Python interpreter
        print("[System] Environment ready! Bootstrapping server inside the venv...\n")
        os.execv(venv_python, [venv_python] + sys.argv)

# Trigger the virtual environment injector immediately on execution
bootstrap_venv()

# --- AT THIS POINT, THE SCRIPT IS GUARANTEED TO BE RUNNING INSIDE THE VENV ---
import json
import threading
import socket
import werkzeug
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from zeroconf import ServiceInfo, Zeroconf

# ... (Rest of your Flask routes, FTP setup, and app.run logic remains exactly the same)


# ... Rest of your application routes and configuration logic


app = Flask(__name__)
app.secret_key = 'xp_sp2_retro_secret'

BASE_STORAGE = os.path.abspath("./ftp_root")
DB_FILE = os.path.abspath("./users_db.json")
os.makedirs(BASE_STORAGE, exist_ok=True)

# --- DATABASE LOGIC ---
def load_db():
    if not os.path.exists(DB_FILE):
        default_db = {
            "admin": {"password": "password123", "role": "admin"},
            "alex": {"password": "pass", "role": "client"},
            "jordan": {"password": "pass", "role": "client"}
        }
        with open(DB_FILE, 'w') as f:
            json.dump(default_db, f, indent=4)
        return default_db
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

USERS_DB = load_db()

def setup_user_directories(username):
    user_root = os.path.join(BASE_STORAGE, username)
    os.makedirs(os.path.join(user_root, "Public"), exist_ok=True)
    os.makedirs(os.path.join(user_root, "Private"), exist_ok=True)
    return user_root

for user in USERS_DB:
    if USERS_DB[user]["role"] == "client":
        setup_user_directories(user)

# --- FTP LAYER ---
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

# --- mDNS ENGINE ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]  # ADD [0] HERE TO EXTRACT JUST THE STRING
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def start_mdns():
    local_ip = get_local_ip()
    packed_ip = socket.inet_aton(local_ip)
    info = ServiceInfo(
        "_http._tcp.local.", "OfficeServer._http._tcp.local.",
        addresses=[packed_ip], port=5000, properties={}, server="officeserver.local."
    )
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    print(f"[mDNS] Active: officeserver.local -> {local_ip}")

ftp_thread = threading.Thread(target=run_ftp_server, daemon=True)
ftp_thread.start()

mdns_thread = threading.Thread(target=start_mdns, daemon=True)
mdns_thread.start()

# --- WEB LAYER ---
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
    return render_template('desktop.html', username=session['username'], role=session.get('role'), clients=clients)

@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    username = request.form.get('username').strip().lower()
    password = request.form.get('password')
    if not username or not password:
        return "Missing fields", 400
    db = load_db()
    if username in db:
        return "User already exists", 400
    db[username] = {"password": password, "role": "client"}
    save_db(db)
    setup_user_directories(username)
    return redirect(url_for('desktop'))

# --- WEB FILES MANAGER (EXPLORER BACKEND) ---
@app.route('/api/explore/<target_user>/<folder_type>')
def explore_folder(target_user, folder_type):
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    current_user = session['username']
    
    if folder_type == "Private" and current_user != target_user and session.get('role') != 'admin':
        return jsonify({"error": "Access Denied to Private Folder"}), 403

    target_path = os.path.join(BASE_STORAGE, target_user, folder_type)
    if not os.path.exists(target_path):
        return jsonify({"error": "Folder not found"}), 404

    files = []
    for item in os.listdir(target_path):
        item_path = os.path.join(target_path, item)
        files.append({
            "name": item,
            "is_dir": os.path.isdir(item_path),
            "size": os.path.getsize(item_path) if not os.path.isdir(item_path) else 0
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
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    target_path = os.path.join(BASE_STORAGE, target_user, folder_type)
    filename = werkzeug.utils.secure_filename(file.filename)
    file.save(os.path.join(target_path, filename))
    return redirect(url_for('desktop'))

@app.route('/api/download/<target_user>/<folder_type>/<filename>')
def download_file(target_user, folder_type, filename):
    if 'username' not in session:
        return "Unauthorized", 401
    
    current_user = session['username']
    if folder_type == "Private" and current_user != target_user and session.get('role') != 'admin':
        return "Access Denied", 403

    target_path = os.path.join(BASE_STORAGE, target_user, folder_type)
    return send_from_directory(target_path, filename, as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
