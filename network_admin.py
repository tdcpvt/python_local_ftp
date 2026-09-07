import socket
from flask import jsonify, request, session

def get_available_ports(host="0.0.0.0", start=5000, end=5020):
    """Scans a safe alternative port range to discover which sockets are completely free."""
    available = []
    for port in range(start, end + 1):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.1)
        try:
            probe.bind((host, port))
            available.append(port)
        except OSError:
            continue
        finally:
            probe.close()
    return available

def register_network_routes(app, load_db, save_db, get_local_ip, LocalNameAdvertisement):
    """Registers the operational API endpoints for network configuration management."""
    
    @app.route('/api/network/status')
    def network_status():
        # Enforce strict session checks on status queries
        if session.get('role') != 'admin':
            return jsonify({"error": "Unauthorized"}), 403

        db = load_db()
        settings = db.get("settings", {})
        current_dns = settings.get("dns_name", "officeserver")
        
        # FIXED: Extract the active running port safely from the browser host header string
        try:
            host_header = request.host  # returns "192.168.1.X:5000"
            if ":" in host_header:
                current_port = int(host_header.split(":")[-1])
            else:
                current_port = 5000
        except Exception:
            current_port = 5000
        
        free_list = get_available_ports()
        return jsonify({
            "current_dns": current_dns,
            "current_port": current_port,
            "available_ports": free_list,
            "local_ip": get_local_ip()
        })

    @app.route('/api/network/rebind', methods=['POST'])
    def network_rebind():
        if session.get('role') != 'admin':
            return jsonify({"error": "Unauthorized"}), 403

        dns_name = request.form.get('dns_name', '').strip().lower()
        target_port = request.form.get('target_port')

        if not dns_name:
            return jsonify({"error": "DNS Name string cannot be blank."}), 400
        try:
            target_port = int(target_port)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid port selection token."}), 400

        # Pull global reference targets to execute live rebind updates
        import __main__
        if hasattr(__main__, 'advertiser') and __main__.advertiser:
            try:
                __main__.advertiser.assign(name=dns_name, ip=get_local_ip(), port=target_port)
                
                # Persist the newly typed configuration to the JSON file database
                db = load_db()
                if "settings" not in db: db["settings"] = {}
                db["settings"]["dns_name"] = dns_name
                save_db(db)
                
                print(f"\n🔄 [mDNS REBIND PORTAL] Network Identity Reconfigured!")
                print(f"👉 Target Domain: http://{dns_name}.local:{target_port}\n")
                
                return jsonify({"status": "success", "dns": dns_name, "port": target_port})
            except Exception as e:
                return jsonify({"error": f"mDNS broadcast rebind failure: {str(e)}"}), 500
        
        return jsonify({"error": "Core advertiser system module inactive."}), 500
