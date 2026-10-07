import os, json, secrets
from flask import Flask, request, jsonify, send_from_directory, session
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("VARNING: SUPABASE_URL eller SUPABASE_KEY saknas!")
    supabase = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase kopplad: " + SUPABASE_URL)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DEFAULT_CATS = ["Bröd & Bageri","Chark & Pålägg","Dryck","Frukt & Grönt","Fryst","Hushåll","Kök","Kött & Fisk","Mejeri & Ost","Skafferi","Snacks & Godis"]

def las_nyckel(nyckel, default):
    if not supabase:
        return default
    try:
        res = supabase.table("torgnota_kategorier").select("varde").eq("nyckel", nyckel).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["varde"]
        return default
    except Exception as e:
        print("Supabase-lasfel:", e)
        return default

def spara_nyckel(nyckel, varde):
    if not supabase:
        print("Sparar ej - supabase ar None")
        return
    try:
        supabase.table("torgnota_kategorier").upsert(
            {"nyckel": nyckel, "varde": varde},
            on_conflict="nyckel"
        ).execute()
        print("Sparat:", nyckel)
    except Exception as e:
        print("Supabase-sparfel:", e)

def load_categories():
    return {
        "categories": las_nyckel("categories", list(DEFAULT_CATS)),
        "assignments": las_nyckel("assignments", {}),
        "borttagna": las_nyckel("borttagna", [])
    }

def save_categories(data):
    if "categories" in data:
        spara_nyckel("categories", data["categories"])
    if "assignments" in data:
        spara_nyckel("assignments", data["assignments"])
    if "borttagna" in data:
        spara_nyckel("borttagna", data["borttagna"])

def load_all_data():
    items = []
    if not os.path.isdir(DATA_DIR):
        return items
    cats = load_categories()
    borttagna = cats.get("borttagna", [])
    for fil in sorted(os.listdir(DATA_DIR)):
        if not fil.endswith(".json"):
            continue
        butik = fil[:-5]
        try:
            with open(os.path.join(DATA_DIR, fil), "r", encoding="utf-8") as f:
                data = json.load(f)
            for p in data:
                p["butik"] = butik
                if p.get("produkt", "").lower().strip() in borttagna:
                    continue
                items.append(p)
        except Exception as e:
            print("Fel i", fil, ":", e)
    return items

def is_admin():
    return session.get("admin") is True

@app.route("/")
def index():
    return send_from_directory(BASE, "index.html")

@app.route("/admin")
def admin():
    return send_from_directory(BASE, "admin.html")

@app.route("/api/data")
def api_data():
    return jsonify({
        "items": load_all_data(),
        "categories": load_categories(),
        "is_admin": is_admin()
    })

@app.route("/api/login", methods=["POST"])
def api_login():
    pw = request.json.get("password", "")
    if pw == ADMIN_PASSWORD:
        session["admin"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Fel losenord"}), 401

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("admin", None)
    return jsonify({"ok": True})

@app.route("/api/assign", methods=["POST"])
def api_assign():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    data = request.json
    produkt = data.get("produkt", "").lower().strip()
    kategori = data.get("kategori", "").strip()
    if not produkt or not kategori:
        return jsonify({"error": "Saknar produkt eller kategori"}), 400
    cats = load_categories()
    if "borttagna" not in cats:
        cats["borttagna"] = []
    if produkt in cats["borttagna"]:
        cats["borttagna"].remove(produkt)
    cats["assignments"][produkt] = kategori
    save_categories(cats)
    return jsonify({"ok": True})

@app.route("/api/assign/remove", methods=["POST"])
def api_assign_remove():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    produkt = request.json.get("produkt", "").lower().strip()
    cats = load_categories()
    if produkt in cats["assignments"]:
        del cats["assignments"][produkt]
        save_categories(cats)
    return jsonify({"ok": True})

@app.route("/api/category/add", methods=["POST"])
def api_category_add():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    namn = request.json.get("namn", "").strip()
    if not namn:
        return jsonify({"error": "Saknar namn"}), 400
    cats = load_categories()
    if namn not in cats["categories"]:
        cats["categories"].append(namn)
        cats["categories"].sort(key=lambda s: s.lower())
        save_categories(cats)
    return jsonify({"ok": True})

@app.route("/api/category/remove", methods=["POST"])
def api_category_remove():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    namn = request.json.get("namn", "").strip()
    cats = load_categories()
    if namn in cats["categories"]:
        cats["categories"].remove(namn)
        cats["assignments"] = {k: v for k, v in cats["assignments"].items() if v != namn}
        save_categories(cats)
    return jsonify({"ok": True})

@app.route("/api/reset", methods=["POST"])
def api_reset():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    save_categories({"categories": list(DEFAULT_CATS), "assignments": {}, "borttagna": []})
    return jsonify({"ok": True})

@app.route("/api/store/upload", methods=["POST"])
def api_store_upload():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    if "file" not in request.files:
        return jsonify({"error": "Ingen fil"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".json"):
        return jsonify({"error": "Endast .json"}), 400
    raw = f.read()
    try:
        json.loads(raw.decode("utf-8"))
    except Exception as e:
        return jsonify({"error": "Ogiltig JSON: " + str(e)}), 400
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f.filename), "wb") as out:
        out.write(raw)
    return jsonify({"ok": True})

@app.route("/api/store/delete", methods=["POST"])
def api_store_delete():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    namn = request.json.get("namn", "").strip()
    if not namn.endswith(".json"):
        namn += ".json"
    path = os.path.join(DATA_DIR, namn)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"ok": True})
    return jsonify({"error": "Filen finns inte"}), 404

@app.route("/api/product/delete", methods=["POST"])
def api_product_delete():
    if not is_admin():
        return jsonify({"error": "Inte inloggad"}), 403
    data = request.json
    produkt = data.get("produkt", "").strip()
    butik = data.get("butik", "").strip()
    if not produkt or not butik:
        return jsonify({"error": "Saknar produkt eller butik"}), 400
    path = os.path.join(DATA_DIR, butik + ".json")
    if not os.path.exists(path):
        return jsonify({"error": "Butiken finns inte"}), 404
    with open(path, "r", encoding="utf-8") as f:
        lista = json.load(f)
    ny = [p for p in lista if p.get("produkt", "").strip() != produkt]
    if len(ny) == len(lista):
        return jsonify({"error": "Produkten hittades inte"}), 404
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ny, f, ensure_ascii=False, indent=2)
    cats = load_categories()
    nyckel = produkt.lower().strip()
    if nyckel in cats["assignments"]:
        del cats["assignments"][nyckel]
    if "borttagna" not in cats:
        cats["borttagna"] = []
    if nyckel not in cats["borttagna"]:
        cats["borttagna"].append(nyckel)
    save_categories(cats)
    return jsonify({"ok": True})

@app.route("/api/stores")
def api_stores():
    stores = []
    if os.path.isdir(DATA_DIR):
        for fil in sorted(os.listdir(DATA_DIR)):
            if fil.endswith(".json"):
                stores.append(fil[:-5])
    return jsonify({"stores": stores})

if __name__ == "__main__":
    print("Lista:  http://localhost:5000")
    print("Admin:  http://localhost:5000/admin")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)