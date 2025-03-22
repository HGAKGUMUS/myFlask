import os
import re
from datetime import datetime
from flask import Flask, request, session, render_template, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "dev_secret_key"  # Üretimde environment variable kullanın
# Dummy commit değişikliği: test için eklendi.

# --------------------------------------
# 1) VERİTABANI AYARI
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

# Kullanıcı temel bilgileri (login vs için)
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)  # Artık "id" adında
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Kullanıcı profili ile bire bir ilişki
    profile = db.relationship("UserProfile", uselist=False, backref="user")

# Kullanıcıya ait detaylı profil bilgileri
class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    name = db.Column(db.String(100))
    zodiac = db.Column(db.String(50))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    height = db.Column(db.Numeric(5,2))
    weight = db.Column(db.Numeric(5,2))
    experience_level = db.Column(db.String(20))
    goals = db.Column(db.Text)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.city_id"))
    district_id = db.Column(db.Integer, db.ForeignKey("districts.district_id"))

# Şehir tablosu
class City(db.Model):
    __tablename__ = "cities"
    city_id = db.Column(db.Integer, primary_key=True)
    city_name = db.Column(db.String(100), nullable=False)
    districts = db.relationship("District", backref="city", lazy=True)

# İlçe tablosu
class District(db.Model):
    __tablename__ = "districts"
    district_id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.city_id"), nullable=False)
    district_name = db.Column(db.String(100), nullable=False)

# Spor kategorileri (örneğin: Futbol, Basketbol vs.)
class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

# Spor programı bilgileri
class Program(db.Model):
    __tablename__ = "programs"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    level = db.Column(db.String(20))  # "Basic" veya "Advanced"
    exercise_steps = db.Column(db.Text)  # Adım adım açıklamalar
    duration = db.Column(db.Integer)      # Dakika cinsinden
    rest_intervals = db.Column(db.Text)
    notes = db.Column(db.Text)
    category = db.relationship('Category', backref=db.backref('programs', lazy=True))

# İzleme logları
class WatchLog(db.Model):
    __tablename__ = "watch_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('watch_logs', lazy=True))
    program = db.relationship('Program', backref=db.backref('watch_logs', lazy=True))

# Kullanıcının seçtiği programı saklamak için (UserProgram)
class UserProgram(db.Model):
    __tablename__ = "user_programs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    start_date = db.Column(db.Date, default=datetime.utcnow)
    progress = db.Column(db.Numeric(5,2), default=0)
    status = db.Column(db.String(20), default="active")
    
    user = db.relationship('User', backref=db.backref('user_programs', lazy=True))
    program = db.relationship('Program', backref=db.backref('user_programs', lazy=True))

# --------------------------------------
# Şifre Validasyonu
# --------------------------------------
def validate_password(pw):
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
# Tabloları Oluşturma ve Örnek Veriler Ekleme
# --------------------------------------
def create_tables():
    # Geliştirme ortamında önce eski tabloları silip yeniden oluşturmak için:
    db.drop_all()
    db.create_all()

    # Şehirler ve ilçeler (örnek veriler)
    if not City.query.first():
        cities = [
            City(city_name="Istanbul"),
            City(city_name="Ankara"),
            City(city_name="Izmir")
        ]
        db.session.add_all(cities)
        db.session.commit()
        istanbul = City.query.filter_by(city_name="Istanbul").first()
        ankara = City.query.filter_by(city_name="Ankara").first()
        izmir = City.query.filter_by(city_name="Izmir").first()
        districts = [
            District(city_id=istanbul.city_id, district_name="Kadıköy"),
            District(city_id=istanbul.city_id, district_name="Beşiktaş"),
            District(city_id=ankara.city_id, district_name="Çankaya"),
            District(city_id=ankara.city_id, district_name="Keçiören"),
            District(city_id=izmir.city_id, district_name="Bornova"),
            District(city_id=izmir.city_id, district_name="Karşıyaka")
        ]
        db.session.add_all(districts)
        db.session.commit()

    # Spor kategorileri ve programları
    if not Category.query.first():
        sports_categories = ["Futbol", "Basketbol", "Tenis", "Yüzme", "Yoga", "Fitness", "Boks", "Koşu"]
        for cat_name in sports_categories:
            cat = Category(name=cat_name)
            db.session.add(cat)
        db.session.commit()
        categories = Category.query.all()
        programs = []
        for cat in categories:
            prog_basic = Program(
                name=f"Beginner {cat.name}",
                category_id=cat.id,
                level="Basic",
                exercise_steps="1. Isınma; 2. Ana Egzersiz; 3. Soğuma",
                duration=30,
                rest_intervals="Set arası 1 dk",
                notes="Doğru formu koruyun."
            )
            prog_advanced = Program(
                name=f"Advanced {cat.name}",
                category_id=cat.id,
                level="Advanced",
                exercise_steps="1. Uzun ısınma; 2. Yoğun egzersiz; 3. Uzun soğuma",
                duration=45,
                rest_intervals="Set arası 1.5 dk",
                notes="Tekniğe odaklanın."
            )
            programs.extend([prog_basic, prog_advanced])
        db.session.add_all(programs)
        db.session.commit()

# --------------------------------------
# GET İle İlçe Verisi Döndürme (AJAX için)
# --------------------------------------
@app.route("/get_districts/<int:city_id>")
def get_districts(city_id):
    districts = District.query.filter_by(city_id=city_id).all()
    district_list = [{"district_id": d.district_id, "district_name": d.district_name} for d in districts]
    return jsonify({"districts": district_list})

# --------------------------------------
# KULLANICI KAYIT (REGISTER)
# --------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        name = request.form.get("name")
        zodiac = request.form.get("zodiac")
        age_str = request.form.get("age")
        city_id = request.form.get("city")
        district_id = request.form.get("district")
        
        # Yeni eklenen alanlar:
        gender = request.form.get("gender")
        height_str = request.form.get("height")
        weight_str = request.form.get("weight")
        experience_level = request.form.get("experience_level")
        goals = request.form.get("goals")
        
        existing = User.query.filter_by(username=username).first()
        if existing:
            flash("Bu kullanıcı adı zaten mevcut!")
            return render_template("register.html", cities=City.query.all())
        
        if not validate_password(password):
            flash("Şifre 8 karakter olmalı ve en az 1 büyük harf, 1 küçük harf, 1 rakam içermelidir.")
            return render_template("register.html", cities=City.query.all())
        
        hashed_pw = generate_password_hash(password)
        try:
            age_val = int(age_str) if age_str else None
        except:
            age_val = None
        try:
            height_val = float(height_str) if height_str else None
        except:
            height_val = None
        try:
            weight_val = float(weight_str) if weight_str else None
        except:
            weight_val = None
        
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        new_profile = UserProfile(
            user_id=new_user.id,
            name=name,
            zodiac=zodiac,
            age=age_val,
            gender=gender,
            height=height_val,
            weight=weight_val,
            experience_level=experience_level,
            goals=goals,
            city_id=int(city_id) if city_id else None,
            district_id=int(district_id) if district_id else None
        )
        db.session.add(new_profile)
        db.session.commit()
        
        flash("Kayıt başarılı! Lütfen giriş yapın.")
        return redirect(url_for("login"))
    
    cities = City.query.all()
    return render_template("register.html", cities=cities)

# --------------------------------------
# KULLANICI GİRİŞ (LOGIN)
# --------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = User.query.filter_by(username=username).first()
        if not user:
            flash("Kullanıcı bulunamadı!")
            return render_template("login.html")
        if check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Giriş başarılı!")
            return redirect(url_for("home"))
        else:
            flash("Yanlış şifre!")
            return render_template("login.html")
    return render_template("login.html")

# --------------------------------------
# ÇIKIŞ (LOGOUT)
# --------------------------------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("Başarıyla çıkış yaptınız.")
    return redirect(url_for("home"))

# --------------------------------------
# ANA SAYFA (HOME)
# --------------------------------------
@app.route("/")
def home():
    user_id = session.get("user_id")
    if user_id:
        user = User.query.get(user_id)
        # Güvenli kontrol: Eğer profil None ise, kullanıcı adını kullan.
        display_name = user.profile.name if user.profile and user.profile.name else user.username
        return render_template("home.html", username=display_name, user_id=user_id)
    return render_template("home.html", username="Ziyaretçi", user_id=None)

# --------------------------------------
# SPOR PROGRAMLARI GÖSTERİMİ (SPORTS)
# --------------------------------------
@app.route("/sports")
def sports():
    programs = Program.query.order_by(Program.name).all()
    return render_template("sports.html", programs=programs)

# --------------------------------------
# KULLANICININ SEÇTİĞİ PROGRAMI İŞLEME (CHOOSE PROGRAM)
# --------------------------------------
@app.route("/choose_program/<int:program_id>")
def choose_program(program_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Önce giriş yapmanız gerekir!")
        return redirect(url_for("login"))
    
    program = Program.query.get(program_id)
    if program:
        # Kullanıcının seçtiği programı UserProgram tablosuna kaydedelim.
        new_user_program = UserProgram(user_id=user_id, program_id=program.id)
        db.session.add(new_user_program)
        db.session.commit()
        
        flash(f"{program.name} programı seçildi ve kaydedildi!")
    else:
        flash("Program bulunamadı!")
    return redirect(url_for("sports"))

# --------------------------------------
# UYGULAMAYI BAŞLAT
# --------------------------------------
if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)
