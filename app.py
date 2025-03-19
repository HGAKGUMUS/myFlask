import os
import re
from datetime import datetime
from flask import Flask, request, session, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "dev_secret_key"  # Production'da environment variable kullanın

# --------------------------------------
# 1) VERITABANI AYARI
# --------------------------------------
db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:932653@localhost:5432/my_flask_db")
db_url = db_url.strip().lstrip("=")

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
    zodiac = db.Column(db.String(50))    # Burç bilgisi
    age = db.Column(db.Integer)
    city = db.Column(db.String(100))       # Şehir
    district = db.Column(db.String(100))   # İlçe

    def __init__(self, username, password, name=None, zodiac=None, age=None, city=None, district=None):
        self.username = username
        self.password = password
        self.name = name
        self.zodiac = zodiac
        self.age = age
        self.city = city
        self.district = district

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
# Şifre Validasyonu
# --------------------------------------
def validate_password(pw):
    # Şifre tam olarak 8 karakter olmalı; eğer minimum 8 karakter isteniyorsa len(pw) < 8 şeklinde değiştirin.
    if len(pw) != 8:
        return False
    if not re.search(r'[A-Z]', pw):
        return False
    if not re.search(r'[a-z]', pw):
        return False
    if not re.search(r'\d', pw):
        return False
    return True

# --------------------------------------
# 3) TABLOLARI OLUŞTURMA ve Spor Kategorileri Ekleme
# --------------------------------------
def create_tables():
    db.create_all()
    if not Category.query.first():
        # Spor dalları listesini oluşturun (örneğin 18 tane; isterseniz genişletebilirsiniz)
        sports_categories = [
            "Futbol", "Basketbol", "Tenis", "Yüzme", "Yoga", "Fitness", "Okçuluk",
            "At Yarışı", "Güreş", "Boks", "Kickbox", "Koşu", "Voleybol",
            "Motor Sporları", "E-Spor", "Atletizm", "Bale", "Bilardo"
        ]
        categories = []
        for cat_name in sports_categories:
            cat = Category(name=cat_name)
            db.session.add(cat)
            categories.append(cat)
        db.session.commit()

        # Her kategori için iki program ekleyelim: Beginner ve Advanced
        programs = []
        for cat in categories:
            prog1 = Program(name=f"Beginner {cat.name}", category_id=cat.id)
            prog2 = Program(name=f"Advanced {cat.name}", category_id=cat.id)
            programs.extend([prog1, prog2])
        db.session.add_all(programs)
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
        zodiac = request.form.get("zodiac")
        city = request.form.get("city")
        district = request.form.get("district")

        # Kullanıcı var mı kontrol
        existing = User.query.filter_by(username=uname).first()
        if existing:
            flash("Bu kullanıcı adı zaten mevcut!")
            return render_template("register.html")

        # Şifre validasyonu
        if not validate_password(pw):
            flash("Şifre 8 karakter olmalı ve en az 1 büyük harf, 1 küçük harf, 1 rakam içermelidir.")
            return render_template("register.html")

        hashed_pw = generate_password_hash(pw)
        try:
            age_val = int(age_str) if age_str else None
        except:
            age_val = None

        new_user = User(
            username=uname,
            password=hashed_pw,
            name=real_name,
            zodiac=zodiac,
            age=age_val,
            city=city,
            district=district
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Kayıt başarılı! Lütfen giriş yapın.")
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
            flash("Kullanıcı bulunamadı!")
            return render_template("login.html")

        if check_password_hash(user.password, pw):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Giriş başarılı!")
            return redirect(url_for("home"))
        else:
            flash("Yanlış şifre!")
            return render_template("login.html")

    return render_template("login.html")

# --------------------------------------
# 6) ÇIKIŞ (LOGOUT)
# --------------------------------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("Başarıyla çıkış yaptınız.")
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
            return render_template("home.html", username=display_name, user_id=user_id, user=user)
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
        html += f"<li>{p.name} (Kategori: {cat_name}) [<a href='/watch/{p.id}'>İZLE</a>]</li>"
    html += "</ul>"
    return html

# --------------------------------------
# 9) PROGRAM İZLEME (WATCH)
# --------------------------------------
@app.route("/watch/<int:program_id>")
def watch_program(program_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Önce giriş yapın!")
        return redirect(url_for("login"))

    prog = Program.query.get(program_id)
    if not prog:
        flash("Program bulunamadı!")
        return redirect(url_for("list_programs"))

    new_log = WatchLog(user_id=user_id, program_id=program_id)
    db.session.add(new_log)
    db.session.commit()

    flash(f"{prog.name} izleniyor...")
    return redirect(url_for("list_programs"))

# --------------------------------------
# 10) SPOR PROGRAMLARI SAYFASI
# --------------------------------------
@app.route("/sports")
def sports():
    programs = Program.query.order_by(Program.name).all()
    html = "<h2>Spor Programları</h2><ul>"
    for prog in programs:
        html += f"<li>{prog.name} (Kategori: {prog.category.name}) - <a href='/watch/{prog.id}'>İZLE</a></li>"
    html += "</ul>"
    return html

# --------------------------------------
# 11) LOG GÖRÜNTÜLEME (OPSİYONEL)
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
        html += f"<p>Kullanıcı: {user_info}, Program: {p.name} (Kategori: {cat_name}), Tarih: {log.watched_at}</p>"
    return html

# --------------------------------------
# 12) UYGULAMAYI BAŞLAT
# --------------------------------------
if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)
