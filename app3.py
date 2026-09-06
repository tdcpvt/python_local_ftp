import os
import json
import datetime
import threading
import socket
import werkzeug
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory

app = Flask(__name__)
app.secret_key = 'xp_sp2_retro_secret'

BASE_STORAGE = os.path.abspath("./ftp_root")
DB_FILE = os.path.abspath("./users_db.json")
os.makedirs(BASE_STORAGE, exist_ok=True)

def load_db():
    if not os.path.exists(DB_FILE):
        default_db = {
            "users": {
                "admin": {"password": "password123", "role": "admin", "can_delete": True},
                "alex": {"password": "pass", "role": "client", "can_delete": False},
                "jordan": {"password": "pass", "role": "client", "can_delete": True}
            },
            "file_registry": []
        }
        with open(DB_FILE, 'w') as f:
            json.dump(default_db, f, indent=4)
        return default_db
    with open(DB_FILE, 'r') as f:
        try:
            data = json.load(f)
            if "file_registry" not in data:
                data["file_registry"] = []
            return data
        except Exception:
            return {"users": {"admin": {"password": "password123", "role": "admin", "can_delete": True}}, "file_registry": []}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

def get_dir_size(path):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

# Initialize storage framework rules
db_init = load_db()
for user in db_init["users"]:
    if db_init["users"][user]["role"] == "client":
        os.makedirs(os.path.join(BASE_STORAGE, user, "Public"), exist_ok=True)
        os.makedirs(os.path.join(user_root := os.path.join(BASE_STORAGE, user), "Private"), exist_ok=True)

# --- FLASK WEB PANEL ROUTES ---
@app.route('/')
def index():
    if 'username' in session: return redirect(url_for('desktop'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    db = load_db()
    if username in db["users"] and db["users"][username]['password'] == password:
        session['username'] = username
        session['role'] = db["users"][username]['role']
        return redirect(url_for('desktop'))
    return "Invalid Credentials", 401

@app.route('/desktop')
def desktop():
    if 'username' not in session: return redirect(url_for('index'))
    db = load_db()
    clients = [u for u, info in db["users"].items() if info['role'] == 'client']
    
    # Calculate Live Storage Quota Metrics
    used_bytes = get_dir_size(BASE_STORAGE)
    used_mb = round(used_bytes / (1024 * 1024), 2)
    
    return render_template('desktop.html', username=session['username'], role=session.get('role'), clients=clients, full_db=db["users"], used_mb=used_mb)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- WEB DATA TRANSMISSION MODULE ENDPOINTS ---
@app.route('/api/explore/<target_user>/<folder_type>')
def explore_folder(target_user, folder_type):
    if 'username' not in session: return jsonify({"error": "Unauthorized"}), 401
    current_user = session['username']
    
    if folder_type == "Private" and current_user != target_user and session.get('role') != 'admin':
        return jsonify({"error": "Access Denied"}), 403

    db = load_db()
    user_permissions = db["users"].get(current_user, {"can_delete": False})
    
    # Filter the registry metadata arrays matching targeted workspace criteria
    matched_files = []
    for f in db["file_registry"]:
        if f["target_user"] == target_user and f["folder_type"] == folder_type:
            file_path = os.path.join(BASE_STORAGE, target_user, folder_type, f["name"])
            if os.path.exists(file_path):
                matched_files.append({
                    "name": f["name"],
                    "size": f["size"],
                    "uploaded_by": f["uploaded_by"],
                    "timestamp": f["timestamp"],
                    "remark": f["remark"],
                    "allow_delete": user_permissions.get("can_delete", False) or session.get('role') == 'admin'
                })
    return jsonify({"files": matched_files})

@app.route('/api/upload/<target_user>/<folder_type>', methods=['POST'])
def upload_file(target_user, folder_type):
    if 'username' not in session: return "Unauthorized", 401
    current_user = session['username']
    
    if folder_type == "Private" and current_user != target_user and session.get('role') != 'admin':
        return "Access Denied", 403

    if 'file' not in request.files: return "No file parameter tracking data", 400
    file = request.files['file']
    if file.filename == '': return "No selected items matching standard targets", 400

    remark = request.form.get('remark', 'No remark provided.').strip()
    if not remark: remark = "No remark provided."

    target_path = os.path.join(BASE_STORAGE, target_user, folder_type)
    filename = werkzeug.utils.secure_filename(file.filename)
    dest_path = os.path.join(target_path, filename)
    
    file.save(dest_path)
    
    # Commit execution meta tags directly to data database loops
    db = load_db()
    # Remove existing entries if file gets overwritten to keep entries distinct
    db["file_registry"] = [x for x in db["file_registry"] if not (x["name"] == filename and x["target_user"] == target_user and x["folder_type"] == folder_type)]
    
    db["file_registry"].append({
        "name": filename,
        "target_user": target_user,
        "folder_type": folder_type,
        "size": os.path.getsize(dest_path),
        "uploaded_by": current_user,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "remark": remark
    })
    save_db(db)
    return redirect(url_for('desktop'))

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    if 'username' not in session: return "Unauthorized", 401
    current_user = session['username']
    db = load_db()
    
    if session.get('role') != 'admin' and not db["users"].get(current_user, {}).get("can_delete", False):
        return "Access Forbidden", 403
        
    target_user = request.form.get('target_user')
    folder_type = request.form.get('folder_type')
    filename = request.form.get('filename')
    
    file_path = os.path.abspath(os.path.join(BASE_STORAGE, target_user, folder_type, werkzeug.utils.secure_filename(filename)))
    if file_path.startswith(BASE_STORAGE) and os.path.exists(file_path):
        os.remove(file_path)
        # Purge indexing records 
        db["file_registry"] = [x for x in db["file_registry"] if not (x["name"] == filename and x["target_user"] == target_user and x["folder_type"] == folder_type)]
        save_db(db)
        return jsonify({"status": "deleted"})
    return "Invalid targeted transaction path tracking parameters", 400

@app.route('/api/download/<target_user>/<folder_type>/<filename>')
def download_file(target_user, folder_type, filename):
    if 'username' not in session: return "Unauthorized", 401
    current_user = session['username']
    if folder_type == "Private" and current_user != target_user and session.get('role') != 'admin':
        return "Access Denied", 403
    return send_from_directory(os.path.join(BASE_STORAGE, target_user, folder_type), werkzeug.utils.secure_filename(filename), as_attachment=True)

@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin': return "Unauthorized", 403
    username = request.form.get('username').strip().lower()
    password = request.form.get('password')
    can_delete = request.form.get('can_delete') == 'true'
    
    db = load_db()
    db["users"][username] = {"password": password, "role": "client", "can_delete": can_delete}
    save_db(db)
    os.makedirs(os.path.join(BASE_STORAGE, username, "Public"), exist_ok=True)
    os.makedirs(os.path.join(BASE_STORAGE, username, "Private"), exist_ok=True)
    return redirect(url_for('desktop'))

@app.route('/admin/delete_user/<username>', methods=['POST'])
def delete_user(username):
    if session.get('role') != 'admin': return "Unauthorized", 403
    db = load_db()
    if username in db["users"] and db["users"][username]['role'] != 'admin':
        del db["users"][username]
        save_db(db)
        return jsonify({"status": "user_removed"})
    return "Invalid tracking target", 400

@app.route('/api/change_password', methods=['POST'])
def change_password():
    if 'username' not in session: return "Unauthorized", 401
    current_user = session['username']
    new_password = request.form.get('new_password')
    db = load_db()
    if current_user in db["users"]:
        db["users"][current_user]['password'] = new_password
        save_db(db)
        return jsonify({"status": "success"})
    return "Error processing user password updates", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
