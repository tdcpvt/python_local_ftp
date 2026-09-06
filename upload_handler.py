import os
import datetime
import werkzeug

# Enforce your default allowed document extensions explicitly
DEFAULT_ALLOWED_EXTENSIONS = {
    'jpeg', 'jpg', 'png', 
    'doc', 'docx', 
    'xls', 'xlsx', 
    'ppt', 'pptx', 
    'pdf', 'txt', 'zip'
}

def get_allowed_extensions(db_config):
    """Extracts extensions allowed by the admin, falling back to defaults."""
    if db_config and "settings" in db_config and "allowed_extensions" in db_config["settings"]:
        return set(db_config["settings"]["allowed_extensions"])
    return DEFAULT_ALLOWED_EXTENSIONS

def process_file_upload(file, target_user, folder_type, current_user, remark, base_storage_path, db_config):
    """
    Executes deep structural validations on incoming files.
    Returns: (tuple) -> (bool: success, str: message_or_filename)
    """
    if not file or file.filename == '':
        return False, "No file selected or empty file packet received."

    # 1. Extract and sanitize file extension
    filename = werkzeug.utils.secure_filename(file.filename)
    if '.' not in filename:
        return False, "File is missing a valid extension."
        
    ext = filename.rsplit('.', 1)[1].lower()
    allowed_exts = get_allowed_extensions(db_config)

    # 2. Enforce strict file extension security block rules
    if ext not in allowed_exts:
        return False, f"Extension '.{ext}' is blocked. Allowed types: {', '.join(sorted(allowed_exts))}"

    # 3. Handle physical storage target directories
    target_dir = os.path.join(base_storage_path, target_user, folder_type)
    os.makedirs(target_dir, exist_ok=True)
    dest_path = os.path.join(target_dir, filename)

    # 4. Save file to mobile disk sandbox
    try:
        file.save(dest_path)
    except Exception as e:
        return False, f"Physical disk write failure: {str(e)}"

    # 5. Build standard structured registry object parameters
    metadata = {
        "name": filename,
        "target_user": target_user,
        "folder_type": folder_type,
        "size": os.path.getsize(dest_path),
        "uploaded_by": current_user,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "remark": remark if remark.strip() else "No remark provided."
    }

    return True, metadata
