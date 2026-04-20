from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from datetime import datetime, timedelta
import os, secrets, string, random, json
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

ADMIN_PASSWORD = "BEBO2026"
KEYS_FILE = "/tmp/keys.json"
USERS_FILE = "/tmp/users.json"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

def load_keys():
    if not os.path.exists(KEYS_FILE): return {}
    with open(KEYS_FILE) as f: return json.load(f)

def save_keys(keys):
    with open(KEYS_FILE, "w") as f: json.dump(keys, f, indent=2)

def load_users():
    if not os.path.exists(USERS_FILE): return {}
    with open(USERS_FILE) as f: return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f: json.dump(users, f, indent=2)

def gen_key():
    chars = string.ascii_uppercase + string.digits
    return "NITRO-" + "".join(random.choices(chars, k=4)) + "-" + "".join(random.choices(chars, k=4)) + "-" + "".join(random.choices(chars, k=4))

def time_remaining(expiry_str):
    try:
        expiry = datetime.fromisoformat(expiry_str)
        now = datetime.now()
        if now > expiry: return "منتهي"
        delta = expiry - now
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes = rem // 60
        if days > 0: return f"{days}d {hours}h"
        elif hours > 0: return f"{hours}h {minutes}m"
        else: return f"{minutes}m"
    except: return "unknown"

@app.route("/public/connect", methods=["POST"])
def public_connect():
    import hashlib, time
    user_key = request.form.get("user_key", "")
    serial = request.form.get("serial", "unknown")
    keys = load_keys()
    if user_key not in keys:
        return jsonify({"status": False, "reason": "Invalid key"})
    k = keys[user_key]
    expiry = datetime.fromisoformat(k["expiry"])
    if datetime.now() > expiry:
        return jsonify({"status": False, "reason": "Key expired"})
    if k.get("disabled", False):
        return jsonify({"status": False, "reason": "Key disabled"})
    max_devices = k.get("max_devices", 1)
    devices = k.get("devices", {})
    if serial not in devices and len(devices) >= max_devices:
        return jsonify({"status": False, "reason": f"Max devices reached ({max_devices})"})
    devices[serial] = {"last_seen": datetime.now().isoformat()}
    keys[user_key]["devices"] = devices
    save_keys(keys)
    rng = int(time.time())
    auth = "PUBG-" + user_key + "-" + serial + "-" + "Vm8Lk7Uj2JmsjCPVPVjrLa7zgfx3uz9E"
    token = hashlib.md5(auth.encode()).hexdigest()
    return jsonify({"status": True, "data": {"token": token, "EXP": k["expiry"], "rng": rng}})

@app.route("/check", methods=["POST"])
def check_key():
    data = request.json
    key = data.get("key", "")
    hwid = data.get("hwid", "unknown")
    device = data.get("device", "unknown")
    keys = load_keys()
    if key not in keys:
        return jsonify({"valid": False, "message": "Invalid key"})
    k = keys[key]
    expiry = datetime.fromisoformat(k["expiry"])
    if datetime.now() > expiry:
        return jsonify({"valid": False, "message": "Key expired"})
    if k.get("disabled", False):
        return jsonify({"valid": False, "message": "Key disabled"})
    max_devices = k.get("max_devices", 1)
    devices = k.get("devices", {})
    if hwid not in devices and len(devices) >= max_devices:
        return jsonify({"valid": False, "message": f"Max devices reached ({max_devices})"})
    devices[hwid] = {"name": device, "last_seen": datetime.now().isoformat()}
    keys[key]["devices"] = devices
    save_keys(keys)
    return jsonify({"valid": True, "message": "OK", "expiry": k["expiry"]})

@app.route("/", methods=["GET"])
def dashboard():
    if not session.get("admin"): return redirect("/login")
    keys = load_keys()
    users = load_users()
    now = datetime.now().isoformat()
    keys_with_remaining = {k: {**v, "remaining": time_remaining(v["expiry"])} for k, v in keys.items()}
    return render_template("dashboard.html", keys=keys_with_remaining, users=users, now=now)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/")
        error = "Wrong password"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/add", methods=["POST"])
def add_key():
    if not session.get("admin"): return redirect("/login")
    keys = load_keys()
    key = request.form.get("key")
    expiry = request.form.get("expiry")
    max_devices = int(request.form.get("max_devices", 1))
    keys[key] = {"expiry": expiry, "max_devices": max_devices, "devices": {}}
    save_keys(keys)
    return redirect("/")

@app.route("/generate", methods=["POST"])
def generate_keys():
    if not session.get("admin"): return redirect("/login")
    keys = load_keys()
    count = int(request.form.get("count", 1))
    days = int(request.form.get("days", 30))
    max_devices = int(request.form.get("max_devices", 1))
    expiry = (datetime.now() + timedelta(days=days)).isoformat()[:16]
    for _ in range(min(count, 100)):
        key = gen_key()
        keys[key] = {"expiry": expiry, "max_devices": max_devices, "devices": {}}
    save_keys(keys)
    return redirect("/")

@app.route("/toggle/<path:key>")
def toggle_key(key):
    if not session.get("admin"): return redirect("/login")
    keys = load_keys()
    if key in keys:
        keys[key]["disabled"] = not keys[key].get("disabled", False)
        save_keys(keys)
    return redirect("/")

@app.route("/extend/<path:key>", methods=["POST"])
def extend_key(key):
    if not session.get("admin"): return redirect("/login")
    keys = load_keys()
    if key in keys:
        days = int(request.form.get("days", 0))
        expiry = datetime.fromisoformat(keys[key]["expiry"])
        expiry = expiry + timedelta(days=days)
        keys[key]["expiry"] = expiry.isoformat()[:16]
        save_keys(keys)
    return redirect("/")

@app.route("/delete_all")
def delete_all():
    if not session.get("admin"): return redirect("/login")
    save_keys({})
    return redirect("/")

@app.route("/delete/<path:key>")
def delete_key(key):
    if not session.get("admin"): return redirect("/login")
    keys = load_keys()
    keys.pop(key, None)
    save_keys(keys)
    return redirect("/")

@app.route("/remove_device/<path:key>/<hwid>")
def remove_device(key, hwid):
    if not session.get("admin"): return redirect("/login")
    keys = load_keys()
    if key in keys and hwid in keys[key].get("devices", {}):
        del keys[key]["devices"][hwid]
        save_keys(keys)
    return redirect("/")

@app.route("/delete_user/<email>")
def delete_user(email):
    if not session.get("admin"): return redirect("/login")
    users = load_users()
    users.pop(email, None)
    save_users(users)
    return redirect("/")

@app.route("/assign_key/<email>", methods=["POST"])
def assign_key(email):
    if not session.get("admin"): return redirect("/login")
    users = load_users()
    if email in users:
        users[email]["key"] = request.form.get("key", "")
        save_users(users)
    return redirect("/")

@app.route("/auth/google")
def auth_google():
    redirect_uri = url_for("auth_google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/auth/google/callback")
def auth_google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info: return redirect("/register")
    email = user_info["email"]
    users = load_users()
    if email not in users:
        users[email] = {"name": user_info.get("name", email), "email": email, "picture": user_info.get("picture", ""), "provider": "google", "joined": datetime.now().isoformat()[:16], "key": ""}
        save_users(users)
    session["user_email"] = email
    return redirect("/user/dashboard")

@app.route("/user/dashboard")
def user_dashboard():
    email = session.get("user_email")
    if not email: return redirect("/register")
    users = load_users()
    user = users.get(email)
    if not user: return redirect("/register")
    keys = load_keys()
    user_key = user.get("key", "")
    key_data = keys.get(user_key) if user_key else None
    return render_template("user_dashboard.html", user=user, key_data=key_data, user_key=user_key, now=datetime.now().isoformat())

@app.route("/user/logout")
def user_logout():
    session.pop("user_email", None)
    return redirect("/register")

@app.route("/register")
def register():
    return render_template("register.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
