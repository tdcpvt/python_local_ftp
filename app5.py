
import os
import json
import threading
import socket
import werkzeug
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from zeroconf import ServiceInfo, Zeroconf

# IMPORT THE NEW SEPARATE SECURE UPLOAD EXTENSION MODULE
import upload_handler


# --- INTEGRATED CUSTOM CLASSES AND PORT UTILITIES ---


class LocalNameAdvertisement:
    """Advertise a chosen .local name while this computer is running."""
    def __init__(self, name: str, ip: str, port: int) -> None:
        self.zeroconf = Zeroconf()
        self.info: ServiceInfo | None = None
        self.assign(name, ip, port)

    def assign(self, name: str, ip: str, port: int) -> None:
        if self.info:
            self.zeroconf.unregister_service(self.info)
        local_host = f"{name}.local."
        self.info = ServiceInfo(
            "_http._tcp.local.", f"{name}._http._tcp.local.",
            addresses=[socket.inet_aton(ip)], port=port,
            properties={b"path": b"/"}, server=local_host,
        )
        self.zeroconf.register_service(self.info)

    def close(self) -> None:
        if self.info: 
            self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()


def free_port(host: str, start: int, end: int) -> int:
    for port in range(start, end + 1):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind((host, port))
            return port
        except OSError:
            continue
        finally:
            probe.close()
    raise RuntimeError(f"No unused port found in {start}-{end}.")

# --- APP CONFIGURATION SETUP MATRICES ---
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
            "settings": {
                "allowed_extensions": list(upload_handler.get_flattened_defaults())
            },
            "file_registry": []
        }
        with open(DB_FILE, 'w') as f:
            json.dump(default_db, f, indent=4)
        return default_db
    with open(DB_FILE, 'r') as f:
        try:
            data = json.load(f)
            if "file_registry" not in data: data["file_registry"] = []
            if "settings" not in data: data["settings"] = {"allowed_extensions": list(upload_handler.get_flattened_defaults())}
            return data
        except Exception:
            return {"users": {"admin": {"password": "password123", "role": "admin", "can_delete": True}}, "settings": {"allowed_extensions": list(upload_handler.get_flattened_defaults())}, "file_registry": []}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

def get_dir_size(path):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(): total += entry.stat().st_size
            elif entry.is_dir(): total += get_dir_size(entry.path)
    except Exception: pass
    return total

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]  # <-- FIXED: Added [0] to extract only the string IP address
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip



# Initialize database mapping profiles
db_init = load_db()
for user in db_init["users"]:
    if db_init["users"][user]["role"] == "client":
        os.makedirs(os.path.join(BASE_STORAGE, user, "Public"), exist_ok=True)
        os.makedirs(os.path.join(BASE_STORAGE, user, "Private"), exist_ok=True)

# --- FLASK WEB ROUTING HANDLERS ---
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
    used_bytes = get_dir_size(BASE_STORAGE)
    used_mb = round(used_bytes / (1024 * 1024), 2)
    return render_template('desktop.html', username=session['username'], role=session.get('role'), clients=clients, full_db=db["users"], used_mb=used_mb)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/explore/<target_user>/<folder_type>')
def explore_folder(target_user, folder_type):
    if 'username' not in session: 
        return jsonify({"error": "Unauthorized"}), 401
    
    current_user = session['username']
    current_role = session.get('role')
    
    # --- FIXED SECURITY PERMISSION MATRIX ---
    # Public folders are ALWAYS open to everyone.
    # Private folders are open ONLY to the owner OR the master admin.
    if folder_type == "Private":
        if current_user != target_user and current_role != 'admin':
            return jsonify({"error": "Access Denied"}), 403

    db = load_db()
    user_permissions = db["users"].get(current_user, {"can_delete": False})
    
    # Ensure physical tracking directories exist safely before reading data tracks
    target_path = os.path.join(BASE_STORAGE, target_user, folder_type)
    if not os.path.exists(target_path):
        os.makedirs(target_path, exist_ok=True)

    matched_files = []
    for f in db["file_registry"]:
        if f["target_user"] == target_user and f["folder_type"] == folder_type:
            if os.path.exists(os.path.join(target_path, f["name"])):
                matched_files.append({
                    "name": f["name"], 
                    "size": f["size"], 
                    "uploaded_by": f["uploaded_by"],
                    "timestamp": f["timestamp"], 
                    "remark": f["remark"],
                    "allow_delete": user_permissions.get("can_delete", False) or current_role == 'admin'
                })
    return jsonify({"files": matched_files})


@app.route('/api/upload/<target_user>/<folder_type>', methods=['POST'])
def upload_file(target_user, folder_type):
    if 'username' not in session: return jsonify({"error": "Unauthorized"}), 401
    current_user = session['username']
    if 'file' not in request.files: return jsonify({"error": "No file found"}), 400
    file = request.files['file']
    remark = request.form.get('remark', 'No remark provided.')
    db = load_db()

    success, result = upload_handler.process_file_upload(
        file=file, target_user=target_user, folder_type=folder_type,
        current_user=current_user, remark=remark, base_storage_path=BASE_STORAGE, db_config=db
    )
    if not success: return jsonify({"error": result}), 400

    db["file_registry"] = [x for x in db["file_registry"] if not (x["name"] == result["name"] and x["target_user"] == target_user and x["folder_type"] == folder_type)]
    db["file_registry"].append(result)
    save_db(db)
    return jsonify({"status": "success", "filename": result["name"]})

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
        db["file_registry"] = [x for x in db["file_registry"] if not (x["name"] == filename and x["target_user"] == target_user and x["folder_type"] == folder_type)]
        save_db(db)
        return jsonify({"status": "deleted"})
    return "Invalid path", 400

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
    return "Invalid user", 400

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
    return "Error updating record", 400

@app.route('/admin/edit_user', methods=['POST'])
def edit_user():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    target_user = request.form.get('target_user')
    new_password = request.form.get('new_password')
    new_role = request.form.get('new_role')
    can_delete = request.form.get('can_delete') == 'true'

    db = load_db()

    if target_user not in db['users']:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

    # Update attributes if provided
    if new_password:
        db['users'][target_user]['password'] = new_password
    if new_role:
        db['users'][target_user]['role'] = new_role
    
    db['users'][target_user]['can_delete'] = can_delete

    save_db(db)
    return jsonify({'status': 'success', 'message': f'User {target_user} updated successfully'})

# --- REGISTER NETWORK ADMIN UTILITIES EXTENSION MODULE ---
import network_admin
network_admin.register_network_routes(app, load_db, save_db, get_local_ip, LocalNameAdvertisement)
import notes_handler
notes_handler.register_notes_routes(app, load_db)


if __name__ == '__main__':
    HOST_INTERFACE = "0.0.0.0"
    RUNTIME_PORT = free_port(HOST_INTERFACE, 5000, 5010)

    LOCAL_IP_STR = get_local_ip()
    advertiser = LocalNameAdvertisement(name="officeserver", ip=LOCAL_IP_STR, port=RUNTIME_PORT)

    print(f"\n=========================================")
    print(f"📡 [mDNS BROADCASTER] Active and Online!")
    print(f"👉 Target Domain: http://officeserver.local:{RUNTIME_PORT}")
    print(f"👉 Local IP Path: http://{LOCAL_IP_STR}:{RUNTIME_PORT}")
    print(f"=========================================\n")

    try:
        app.run(host=HOST_INTERFACE, port=RUNTIME_PORT)
    finally:
        # Graceful exit executing the cleanup sequence
        advertiser.close()



