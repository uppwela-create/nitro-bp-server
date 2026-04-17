from flask import Flask, request, jsonify, render_template, redirect, session
from datetime import datetime
import json, os, secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

ADMIN_PASSWORD = "BEBO2026"
KEYS_FILE = "keys.json"

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}
    with open(KEYS_FILE) as f:
        return json.load(f)

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

@app.route("/check", methods=["POST"])
def check_key():
    data = request.json
    key = data.get("key", "")
    keys = load_keys()
    if key not in keys:
        return jsonify({"valid": False, "message": "Invalid key"})
    expiry = datetime.fromisoformat(keys[key]["expiry"])
    if datetime.now() > expiry:
        return jsonify({"valid": False, "message": "Key expired"})
    return jsonify({"valid": True, "message": "OK", "expiry": keys[key]["expiry"]})

@app.route("/", methods=["GET", "POST"])
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
    keys[key] = {"expiry": expiry}
    save_keys(keys)
    return redirect("/")

@app.route("/delete/<key>")
def delete_key(key):
    if not session.get("admin"):
        return redirect("/login")
    keys = load_keys()
    keys.pop(key, None)
    save_keys(keys)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
