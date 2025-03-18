import os
from datetime import datetime
from flask import Flask, request, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "dev_secret_key"  # Production'da environment variable kullan

# --------------------------------------
# 1) VERITABANI AYARI
# --------------------------------------
# 1) VERITABANI AYARI
# --------------------------------------
db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:932653@localhost:5432/my_flask_db")
db_url = db_url.strip().lstrip("=")  # Başındaki boşluk ve '=' işaretini temizler.

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False



db = SQLAlchemy(app)

# --------------------------------------
# 2) MODELLER (Tablolar)
# --------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    preferences = db.Column(db.String(200))

    def __init__(self, username, password, name=None, age=None, preferences=None):
        self.username = username
        self.password = password
        self.name = name
        self.age = age
        self.preferences = preferences

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Program(db.Model):
    __tablename__ = "programs"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    category = db.relationship('Category', backref=db.backref('programs', lazy=True))

class WatchLog(db.Model):
    __tablename__ = "watch_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('watch_logs', lazy=True))
    program = db.relationship('Program', backref=db.backref('watch_logs', lazy=True))

# --------------------------------------
# 3) TABLOLARI OLUŞTURMA
# --------------------------------------
def create_tables():
    db.create_all()
    if not Category.query.first():
        cat1 = Category(name="Yoga")
        cat2 = Category(name="Cardio")
        cat3 = Category(name="Pilates")
        db.session.add_all([cat1, cat2, cat3])
        db.session.commit()

        p1 = Program(name="Yoga Basics", category_id=cat1.id)
        p2 = Program(name="Advanced Yoga", category_id=cat1.id)
        p3 = Program(name="Cardio Burn", category_id=cat2.id)
        p4 = Program(name="Pilates Intro", category_id=cat3.id)
        db.session.add_all([p1, p2, p3, p4])
        db.session.commit()

# --------------------------------------
# 4) KULLANICI KAYIT (REGISTER)
# --------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uname = request.form.get("username")
        pw = request.form.get("password")
        real_name = request.form.get("name")
        age_str = request.form.get("age")
        prefs = request.form.get("preferences")

        # Kullanıcı var mı kontrol
        existing = User.query.filter_by(username=uname).first()
        if existing:
            return "Bu kullanıcı adı var!", 400

        hashed_pw = generate_password_hash(pw)
        try:
            age_val = int(age_str) if age_str else None
        except:
            age_val = None

        new_user = User(
            username=uname,
            password=hashed_pw,
            name=real_name,
            age=age_val,
            preferences=prefs
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")

# --------------------------------------
# 5) KULLANICI GİRİŞ (LOGIN)
# --------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form.get("username")
        pw = request.form.get("password")

        user = User.query.filter_by(username=uname).first()
        if not user:
            return "Kullanıcı yok!", 404

        if check_password_hash(user.password, pw):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("home"))
        else:
            return "Yanlış şifre!", 401

    return render_template("login.html")

# --------------------------------------
# 6) ÇIKIŞ (LOGOUT)
# --------------------------------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return redirect(url_for("home"))

# --------------------------------------
# 7) ANA SAYFA (HOME)
# --------------------------------------
@app.route("/")
def home():
    user_id = session.get("user_id")
    if user_id:
        user = User.query.get(user_id)
        if user:
            display_name = user.name if user.name else user.username
            return render_template(
                "home.html",
                username=display_name,
                user_id=user_id,
                user=user
            )
    # Kullanıcı yoksa veya user_id bulunamadıysa
    return render_template("home.html", username=None, user_id=None, user=None)

# --------------------------------------
# 8) PROGRAM / KATEGORİ GÖRÜNTÜLEME
# --------------------------------------
@app.route("/programs")
def list_programs():
    progs = Program.query.all()
    html = "<h2>Spor Programları</h2><ul>"
    for p in progs:
        cat_name = p.category.name if p.category else "Bilinmiyor"
        html += f"<li>{p.name} (Kategori: {cat_name}) "
        html += f"[<a href='/watch/{p.id}'>İZLE</a>]</li>"
    html += "</ul>"
    return html

# --------------------------------------
# 9) PROGRAM İZLEME (WATCH)
# --------------------------------------
@app.route("/watch/<int:program_id>")
def watch_program(program_id):
    user_id = session.get("user_id")
    if not user_id:
        return "Önce giriş yapın!", 401

    prog = Program.query.get(program_id)
    if not prog:
        return "Program yok!", 404

    cat_name = prog.category.name if prog.category else "Kategorisi Yok"
    new_log = WatchLog(user_id=user_id, program_id=program_id)
    db.session.add(new_log)
    db.session.commit()

    return f"""
    <h2>{prog.name} İzleniyor...</h2>
    <p>Kategori: {cat_name}</p>
    <p>Log kaydedildi.</p>
    <p><a href='/programs'>Geri Dön</a></p>
    """

# --------------------------------------
# 10) LOG GÖRÜNTÜLEME (OPSİYONEL)
# --------------------------------------
@app.route("/logs")
def show_logs():
    logs = WatchLog.query.order_by(WatchLog.watched_at.desc()).all()
    html = "<h2>İzleme Logları</h2>"
    for log in logs:
        u = log.user
        p = log.program
        user_info = f"{u.username} / {u.name}" if (u and u.name) else (u.username if u else "Bilinmiyor")
        cat_name = p.category.name if p.category else "Bilinmiyor"
        html += f"""
        <p>
        Kullanıcı: {user_info},
        Program: {p.name} (Kategori: {cat_name}),
        Tarih: {log.watched_at}
        </p>
        """
    return html

# --------------------------------------
# 11) UYGULAMAYI BAŞLAT
# --------------------------------------
if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)
