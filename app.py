import os
import re
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text  # Eklenen import
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from catboost import CatBoostRegressor
from sqlalchemy import func    # zaten or_, text var; func yoksa ekle


app = Flask(__name__)
app.secret_key = "dev_secret_key"  # Üretimde environment variable kullanın

# --------------------------------------
# 1) VERİTABANI AYARI
# --------------------------------------
default_db_url = "postgresql://postgres:LKLdBTyibvuWNWGBSdgdUvniNRPJQTwG@switchyard.proxy.rlwy.net:15854/railway?options=-c%20search_path=public"
db_url = os.environ.get("DATABASE_URL", default_db_url)
db_url = db_url.strip().lstrip("=")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --------------------------------------
# Helper Fonksiyonu
# --------------------------------------
def get_checkbox_values(field):
    # Checkbox alanından gelen birden fazla değeri liste olarak alır, virgülle ayrılmış string döndürür.
    values = request.form.getlist(field)
    return ",".join(values) if values else None

# --------------------------------------
# 2) MODELLER (Tablolar)
# --------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile = db.relationship("UserProfile", uselist=False, backref="user")

class UserProfile(db.Model):
    __tablename__ = "user_profiles"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    name = db.Column(db.String(100))
    zodiac = db.Column(db.String(50))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))   # female, male, other
    height = db.Column(db.Numeric(5,2))
    weight = db.Column(db.Numeric(5,2))
    experience_level = db.Column(db.String(20))  # Beginner, Intermediate, Advanced
    goals = db.Column(db.Text)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.city_id"))
    district_id = db.Column(db.Integer, db.ForeignKey("districts.district_id"))
    # Yeni eklenen alanlar:
    injury_history = db.Column(db.Text)  # Eğer ileride kullanmak isterseniz (HTML'de yer yoksa boş bırakılabilir)
    surgery_history = db.Column(db.String(100))
    medications = db.Column(db.Text)
    chronic_conditions = db.Column(db.Text)
    activity_level = db.Column(db.String(20))  # Eğer HTML'de eklenmezse None kalır
    nutrition = db.Column(db.String(20))       # Eğer HTML'de eklenmezse None kalır
    supplement_usage = db.Column(db.Text)
    daily_water_intake = db.Column(db.String(20))

class City(db.Model):
    __tablename__ = "cities"
    city_id = db.Column(db.Integer, primary_key=True)
    city_name = db.Column(db.String(100), nullable=False)
    districts = db.relationship("District", backref="city", lazy=True)

class District(db.Model):
    __tablename__ = "districts"
    district_id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.city_id"), nullable=False)
    district_name = db.Column(db.String(100), nullable=False)

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Program(db.Model):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    level = db.Column(db.String(20))   # Beginner, Intermediate, Advanced
    exercise_steps = db.Column(db.Text)
    duration = db.Column(db.Integer)
    rest_intervals = db.Column(db.Text)
    notes = db.Column(db.Text)
    gender = db.Column(db.String(10), default="unisex")  # female, male, unisex
    category = db.relationship('Category', backref=db.backref('programs', lazy=True))
    difficulty = db.Column(db.Integer)  # Program zorluk seviyesi
    type = db.Column(db.String(50))      # Program türü (örn. Kardiyo, Ağırlık)

class UserProgramRating(db.Model):
    __tablename__ = 'user_program_ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 arası puan
    feedback = db.Column(db.Text)                   # Yorum
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    duration = db.Column(db.Integer)                # Kullanım süresi (dakika)
    progress = db.Column(db.Float)                  # İlerleme (%)

class WatchLog(db.Model):
    __tablename__ = "watch_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('watch_logs', lazy=True))
    program = db.relationship('Program', backref=db.backref('watch_logs', lazy=True))

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
    db.create_all()
    db.session.commit()

    # Şehirler ve ilçeler ekleme
    if not City.query.first():
        cities = [
            City(city_name="Istanbul"),
            City(city_name="Ankara"),
            City(city_name="Izmir"),
            City(city_name="Eskişehir")
        ]
        db.session.add_all(cities)
        db.session.commit()

        # İstanbul ilçeleri (örnek)
        istanbul = City.query.filter_by(city_name="Istanbul").first()
        istanbul_districts = ["Kadıköy", "Beşiktaş", "Üsküdar", "Sarıyer", "Bakırköy", "Ataşehir"]
        for dist in istanbul_districts:
            db.session.add(District(city_id=istanbul.city_id, district_name=dist))
        
        # Ankara ilçeleri (örnek)
        ankara = City.query.filter_by(city_name="Ankara").first()
        ankara_districts = ["Çankaya", "Keçiören", "Altındağ", "Mamak", "Etimesgut"]
        for dist in ankara_districts:
            db.session.add(District(city_id=ankara.city_id, district_name=dist))
        
        # İzmir ilçeleri (örnek)
        izmir = City.query.filter_by(city_name="Izmir").first()
        izmir_districts = ["Bornova", "Karşıyaka", "Konak", "Buca", "Alsancak"]
        for dist in izmir_districts:
            db.session.add(District(city_id=izmir.city_id, district_name=dist))
        
        # Eskişehir ilçeleri - sadece "Odunpazarı" ve "Tepebaşı"
        eskisehir = City.query.filter_by(city_name="Eskişehir").first()
        eskisehir_districts = ["Odunpazarı", "Tepebaşı"]
        for dist in eskisehir_districts:
            db.session.add(District(city_id=eskisehir.city_id, district_name=dist))
        
        db.session.commit()

    if not Category.query.first():
        sports_categories = ["Futbol", "Basketbol", "Tenis", "Yüzme", "Yoga", "Fitness", "Boks", "Koşu"]
        for cat_name in sports_categories:
            cat = Category(name=cat_name)
            db.session.add(cat)
        db.session.commit()
        categories = Category.query.all()

        programs = []
        for cat in categories:
            prog_basic_f = Program(
                name=f"Beginner {cat.name} (Kadın)",
                category_id=cat.id,
                level="Beginner",
                exercise_steps="1. Isınma; 2. Ana Egzersiz; 3. Soğuma",
                duration=30,
                rest_intervals="Set arası 1 dk",
                notes="Doğru formu koruyun.",
                gender="female",
                difficulty=1,
                type=cat.name
            )
            prog_basic_m = Program(
                name=f"Beginner {cat.name} (Erkek)",
                category_id=cat.id,
                level="Beginner",
                exercise_steps="1. Isınma; 2. Ana Egzersiz; 3. Soğuma",
                duration=30,
                rest_intervals="Set arası 1 dk",
                notes="Temel hareketler, form önemli.",
                gender="male",
                difficulty=1,
                type=cat.name
            )
            prog_adv_f = Program(
                name=f"Advanced {cat.name} (Kadın)",
                category_id=cat.id,
                level="Advanced",
                exercise_steps="1. Uzun ısınma; 2. Yoğun egzersiz; 3. Uzun soğuma",
                duration=45,
                rest_intervals="Set arası 1.5 dk",
                notes="Ağır kilolarda dikkat.",
                gender="female",
                difficulty=3,
                type=cat.name
            )
            prog_adv_m = Program(
                name=f"Advanced {cat.name} (Erkek)",
                category_id=cat.id,
                level="Advanced",
                exercise_steps="1. Uzun ısınma; 2. Yoğun egzersiz; 3. Uzun soğuma",
                duration=45,
                rest_intervals="Set arası 1.5 dk",
                notes="Ağır çalışmada form çok önemli.",
                gender="male",
                difficulty=3,
                type=cat.name
            )
            programs.extend([prog_basic_f, prog_basic_m, prog_adv_f, prog_adv_m])

        prog_split_basic_f = Program(
            name="Beginner 3-Day Split (Kadın)",
            category_id=3,
            level="Beginner",
            exercise_steps="Day 1: Üst Vücut; Day 2: Bacak & Karın; Day 3: Kardiyo & Full Body",
            duration=35,
            rest_intervals="Set arası 1 dk, günler arasında 1 gün dinlenme",
            notes="Yeni başlayan kadınlar için 3 günlük program.",
            gender="female",
            difficulty=2,
            type="Fitness"
        )
        prog_split_basic_m = Program(
            name="Beginner 3-Day Split (Erkek)",
            category_id=3,
            level="Beginner",
            exercise_steps="Day 1: Üst Vücut; Day 2: Bacak & Karın; Day 3: Kardiyo & Full Body",
            duration=40,
            rest_intervals="Set arası 1 dk, günler arasında 1 gün dinlenme",
            notes="Yeni başlayan erkekler için 3 günlük program.",
            gender="male",
            difficulty=2,
            type="Fitness"
        )
        prog_split_adv_f = Program(
            name="Advanced 3-Day Split (Kadın)",
            category_id=3,
            level="Advanced",
            exercise_steps="Day 1: Göğüs & Sırt; Day 2: Bacak & Karın; Day 3: Omuz & Kardiyo",
            duration=60,
            rest_intervals="Set arası 1.5-2 dk, günler arasında 1 gün dinlenme",
            notes="İleri seviye kadınlar için split program.",
            gender="female",
            difficulty=4,
            type="Fitness"
        )
        prog_split_adv_m = Program(
            name="Advanced 3-Day Split (Erkek)",
            category_id=3,
            level="Advanced",
            exercise_steps="Day 1: Göğüs & Sırt; Day 2: Bacak & Karın; Day 3: Omuz & Kardiyo",
            duration=70,
            rest_intervals="Set arası 1.5-2 dk, günler arasında 1 gün dinlenme",
            notes="İleri seviye erkekler için split program.",
            gender="male",
            difficulty=4,
            type="Fitness"
        )
        programs.extend([prog_split_basic_f, prog_split_basic_m, prog_split_adv_f, prog_split_adv_m])
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
        
        # Mevcut alanlar:
        gender = request.form.get("gender")
        height_str = request.form.get("height")
        weight_str = request.form.get("weight")
        experience_level = request.form.get("experience_level")
        goals = request.form.get("goals")
        
        # Yeni eklenen alanlar:
        # "Kronik Hastalıklar" checkbox alanından gelen verileri alıyoruz.
        chronic_conditions = get_checkbox_values("chronic_conditions_options")
        # "Ameliyat Geçmişi" dropdown seçim değeri:
        surgery_history = request.form.get("surgery_history")
        # İlaç kullanımı için radyo buton değeri:
        drug_usage = request.form.get("drug_usage")  # "evet" veya "hayır"
        # Eğer "evet" ise ilaç seçimi checkboxlarından gelen verileri alıyoruz.
        medications = get_checkbox_values("drug_options") if drug_usage == "evet" else None
        # Supplement kullanımı checkboxlarından gelen verileri alıyoruz.
        supplement_usage = get_checkbox_values("supplement_options")
        # Günlük su miktarı dropdown değeri:
        daily_water_intake = request.form.get("daily_water_intake")
        
        # activity_level ve nutrition HTML formunda alan yoksa None kalır.
        activity_level = request.form.get("activity_level")
        nutrition = request.form.get("nutrition")
        
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
            district_id=int(district_id) if district_id else None,
            chronic_conditions=chronic_conditions,
            surgery_history=surgery_history,
            medications=medications,
            supplement_usage=supplement_usage,
            daily_water_intake=daily_water_intake,
            activity_level=activity_level,
            nutrition=nutrition
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
        if not user:
            session.clear()
            flash("Kullanıcı bulunamadı, lütfen tekrar giriş yapın.")
            return redirect(url_for("login"))
        display_name = user.profile.name if user.profile and user.profile.name else user.username
        return render_template("home.html", username=display_name, user_id=user_id)
    return render_template("home.html", username="Ziyaretçi", user_id=None)
    
    
# --------------------------------------
# Basit öneri motoru (cinsiyet + seviye + puan)
# --------------------------------------
def recommend_for_user(user, limit=6):
    auto_gender = user.profile.gender or "unisex"
    auto_level  = (user.profile.experience_level or "").lower()

    q = (
        db.session.query(Program, func.avg(UserProgramRating.rating).label("avg_r"))
        .outerjoin(UserProgramRating, Program.id == UserProgramRating.program_id)
        .filter(
            (Program.gender == auto_gender) | (Program.gender == "unisex")
        )
        .group_by(Program.id)
    )
    if auto_level:
        q = q.filter(func.lower(Program.level) == auto_level)

    # sırala: yüksek puan önce, oy azsa yine de gelsin
    return [p for p, _ in q.order_by(func.avg(UserProgramRating.rating).desc()).limit(limit)]    

# --------------------------------------
# SPOR PROGRAMLARI GÖSTERİMİ (SPORTS)
# --------------------------------------
@app.route("/sports")
def sports():
    user_id = session.get("user_id")
    if not user_id:
        flash("Programları görmek için önce giriş yapın.")
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user or not user.profile:
        flash("Profil bilgileriniz eksik. Lütfen profilinizi güncelleyin.")
        return redirect(url_for("home"))

    from sqlalchemy import or_, func
    show_all = request.args.get("show_all", "false").lower() == "true"
    query = Program.query
    if not show_all:
        auto_gender = user.profile.gender if user.profile.gender else "unisex"
        auto_level  = user.profile.experience_level.strip() if user.profile.experience_level else ""
        query = query.filter(or_(Program.gender == auto_gender, Program.gender == "unisex"))
        if auto_level:
            query = query.filter(func.lower(Program.level) == auto_level.lower())

    programs = query.order_by(Program.name).all()

    # >>> yeni satır – doğru girintiyle <<<
    recommended_programs = recommend_for_user(user)

    return render_template(
        "sports.html",
        programs=programs,
        recommended_programs=recommended_programs
    )

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
        new_user_program = UserProgram(user_id=user_id, program_id=program_id)
        db.session.add(new_user_program)
        db.session.commit()
        flash(f"{program.name} programı seçildi ve kaydedildi!")
    else:
        flash("Program bulunamadı!")
    return redirect(url_for("sports"))

# --------------------------------------
# Program için ortalama puan & toplam oy
# --------------------------------------
def program_stats(program_id):
    avg_rating, num_ratings = (
        db.session.query(
            func.coalesce(func.avg(UserProgramRating.rating), 0),
            func.count(UserProgramRating.id)
        )
        .filter(UserProgramRating.program_id == program_id)
        .first()
    )
    return float(avg_rating), int(num_ratings)    
    
        #  <<<  BURAYA EKLE >>>
    app.jinja_env.globals["program_stats"] = program_stats
    
    # --------------------------------------
# PROGRAMI PUANLAMA (RATE PROGRAM)
# --------------------------------------
@app.route("/rate_program/<int:program_id>", methods=["GET", "POST"])
def rate_program(program_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Puan vermek için önce giriş yapın.")
        return redirect(url_for("login"))

    program = Program.query.get_or_404(program_id)

    if request.method == "POST":
        rating   = int(request.form.get("rating", 0))
        feedback = request.form.get("feedback")
        duration = request.form.get("duration")
        progress = request.form.get("progress")

        new_rating = UserProgramRating(
            user_id   = user_id,
            program_id= program_id,
            rating    = rating,
            feedback  = feedback,
            duration  = int(duration) if duration else None,
            progress  = float(progress) if progress else None
        )
        db.session.add(new_rating)
        db.session.commit()

        flash("Puanınız kaydedildi, teşekkürler!")
        return redirect(url_for("sports"))

    # GET isteği ise formu göster
    return render_template("rate_program.html", program=program)


# --------------------------------------
# PROFİL SAYFASI (YENİ) - Kullanıcının detaylarını gösterir
# --------------------------------------
@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        flash("Profil sayfasına erişmek için lütfen giriş yapın.")
        return redirect(url_for("login"))
    
    user = User.query.get(user_id)
    if not user or not user.profile:
        flash("Profil bilgileriniz bulunamadı. Lütfen bilgilerinizi kaydedin.")
        return redirect(url_for("home"))
    
    return render_template("profile.html", user=user, profile=user.profile)

# --------------------------------------
# UYGULAMAYI BAŞLAT
# --------------------------------------
if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)
