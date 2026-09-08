import os
import json
from datetime import datetime
from flask import jsonify, request, session, render_template

NOTES_DB_FILE = os.path.abspath("./notes_db.json")

def load_notes_db():
    if not os.path.exists(NOTES_DB_FILE):
        default_notes = {"messages": []}
        with open(NOTES_DB_FILE, 'w') as f:
            json.dump(default_notes, f, indent=4)
        return default_notes
    with open(NOTES_DB_FILE, 'r') as f:
        try:
            return json.load(f)
        except Exception:
            return {"messages": []}

def save_notes_db(data):
    with open(NOTES_DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def register_notes_routes(app, load_main_db):
    
    @app.route('/api/notes/list', methods=['GET'])
    def get_notes():
        if 'username' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        current_user = session['username']
        notes_db = load_notes_db()
        
        # Privacy Constraint: Filter messages strictly where recipient matches logged-in user
        user_messages = [
            msg for msg in notes_db.get("messages", [])
            if msg.get("recipient") == current_user
        ]
        
        return jsonify({"messages": user_messages})

    @app.route('/api/notes/send', methods=['POST'])
    def send_note():
        if 'username' not in session:
            return jsonify({"error": "Unauthorized"}), 401
            
        sender = session['username']
        recipient = request.form.get('recipient')
        body = request.form.get('body', '').strip()
        flag = request.form.get('flag', 'Note')
        
        valid_flags = ["Important", "Note", "Look At"]
        if flag not in valid_flags:
            flag = "Note"
            
        if not recipient or not body:
            return jsonify({"error": "Recipient and message body are required."}), 400
            
        # Verify recipient exists in the system
        main_db = load_main_db()
        if recipient not in main_db.get("users", {}):
            return jsonify({"error": "Recipient user does not exist."}), 404

        new_message = {
            "id": len(load_notes_db().get("messages", [])) + 1,
            "sender": sender,
            "recipient": recipient,
            "body": body,
            "flag": flag,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        notes_db = load_notes_db()
        notes_db["messages"].append(new_message)
        save_notes_db(notes_db)

        return jsonify({"status": "success", "message": "Note sent successfully."})

    @app.route('/api/notes/delete', methods=['POST'])
    def delete_note():
        if 'username' not in session:
            return jsonify({"error": "Unauthorized"}), 401
            
        current_user = session['username']
        msg_id = request.form.get('msg_id')

        if not msg_id:
            return jsonify({"error": "Message ID required"}), 400

        notes_db = load_notes_db()
        messages = notes_db.get("messages", [])

        # Find the message index
        target_msg = None
        for msg in messages:
            if str(msg.get("id")) == str(msg_id):
                target_msg = msg
                break

        if not target_msg:
            return jsonify({"error": "Message not found"}), 404

        # Security check: User must be either the Sender OR Receiver to delete
        if target_msg.get("sender") != current_user and target_msg.get("recipient") != current_user:
            return jsonify({"error": "Access Denied: You cannot delete this note."}), 403

        # Remove message from array and persist to database
        notes_db["messages"] = [m for m in messages if str(m.get("id")) != str(msg_id)]
        save_notes_db(notes_db)

        return jsonify({"status": "success", "message": "Note deleted successfully."})