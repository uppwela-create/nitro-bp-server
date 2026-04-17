from flask import Flask, request, jsonify, render_template, redirect, session
from datetime import datetime, timedelta
import os, secrets, string, random, json

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

ADMIN_PASSWORD = "BEBO2026"

# Redis
import redis
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL, decode_responses=True)

def load_keys():
    data = r.get("keys")
    if not data:
        return {}
    return json.loads(data)

def save_keys(keys):
    r.set("keys", json.dumps(keys))

def gen_key():
    chars = string.ascii_uppercase + string.digits
    return "NITRO-" + "".join(random.choices(chars, k=4)) + "-" + "".join(random.choices(chars, k=4)) + "-" + "".join(random.choices(chars, k=4))

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
    if not session.get("admin"):
        return redirect("/login")
    keys = load_keys()
    now = datetime.now().isoformat()
    return render_template("dashboard.html", keys=keys, now=now)

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
    if not session.get("admin"):
        return redirect("/login")
    keys = load_keys()
    key = request.form.get("key")
    expiry = request.form.get("expiry")
    max_devices = int(request.form.get("max_devices", 1))
    keys[key] = {"expiry": expiry, "max_devices": max_devices, "devices": {}}
    save_keys(keys)
    return redirect("/")

@app.route("/generate", methods=["POST"])
def generate_keys():
    if not session.get("admin"):
        return redirect("/login")
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

@app.route("/delete_all")
def delete_all():
    if not session.get("admin"):
        return redirect("/login")
    save_keys({})
    return redirect("/")

@app.route("/delete/<path:key>")
def delete_key(key):
    if not session.get("admin"):
        return redirect("/login")
    keys = load_keys()
    keys.pop(key, None)
    save_keys(keys)
    return redirect("/")

@app.route("/remove_device/<path:key>/<hwid>")
def remove_device(key, hwid):
    if not session.get("admin"):
        return redirect("/login")
    keys = load_keys()
    if key in keys and hwid in keys[key].get("devices", {}):
        del keys[key]["devices"][hwid]
        save_keys(keys)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
