import os
import re
from datetime import datetime, date, timezone



from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import text, or_, func, case
from sqlalchemy.exc import IntegrityError


import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from xgboost import XGBRegressor
from catboost import CatBoostRegressor

import joblib
import json
from pathlib import Path

# ---------------------------------
# 0) Model metrics (RMSE & tarih) yükle
# ---------------------------------
METRICS_PATH = Path(__file__).parent / "models" / "metrics.json"

def load_model_metrics():
    if METRICS_PATH.exists():
        with open(METRICS_PATH) as f:
            data = json.load(f)
            # UTC timestamp string → datetime objesi (isteğe bağlı)
            try:
                data["trained_at"] = datetime.fromisoformat(data["trained_at"])
            except Exception:
                pass
            return data
    return {"rmse": None, "trained_at": None}

model_metrics = load_model_metrics()

# Jinja’dan erişilebilsin
# (app tanımlandıktan sonra da çalışır ama şimdilik import’ların ardından)
# Seçeceğiniz yere taşıyabilirsiniz.
# Aşağıda app = Flask(...)’den hemen sonra global olarak da kaydediyoruz.

# ---------------------------------
# Pipeline'ı yükle
# ---------------------------------
PIPELINE_PATH = os.path.join(os.path.dirname(__file__), "models", "fit_pipeline.pkl")
pipeline      = joblib.load(PIPELINE_PATH) if os.path.exists(PIPELINE_PATH) else None

# ---------------------------------
# Tahmin yardımcı fonksiyonu
# ---------------------------------
def predict_score(user, program):
    if pipeline is None:
        return 0
    feats = {
        "age": user.profile.age,
        "height": float(user.profile.height),
        "weight": float(user.profile.weight),
        "duration": program.duration,
        "gender": user.profile.gender,
        "experience_level": user.profile.experience_level,
        "program_level": program.level,
        "type": program.type
    }
    return pipeline.predict(pd.DataFrame([feats]))[0]


app = Flask(__name__)
app.secret_key = "dev_secret_key"

# Jinja’ya modeli ve metrikleri aç
app.jinja_env.globals["pipeline"]       = pipeline
app.jinja_env.globals["predict_score"]  = predict_score
app.jinja_env.globals["model_metrics"]  = model_metrics

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
    city     = db.relationship("City",     backref="profiles", lazy="joined")
    district = db.relationship("District", backref="profiles", lazy="joined")
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
        # 🆕  --- meta sütunları ---
    days_per_week = db.Column(db.Integer)        # 1 · 3 · 5
    focus_area    = db.Column(db.String(30))      # Full Body · Split
    weeks_total   = db.Column(db.Integer)         # opsiyonel
    @property
    def recommended_rest(self):
        """
        notes içinden 'Her set arasında yaklaşık X dinlenme yapın.' cümlesinden
        sadece X kısmını çeker (örn. '60-90 saniye').
        """
        if not self.notes:
            return None
        # 'dinlenme' kelimesi öncesindeki metni alıyoruz
        m = re.search(r"Her set arasında yaklaşık\s+(.+?)\s+dinlenme", self.notes)
        return m.group(1).strip() if m else None


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
    
class Movement(db.Model):
    __tablename__ = "movements"
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    url  = db.Column(db.String(255))  # boş kalabilir, siz dolduracaksınız
    
@app.route("/movements")
def movements():
    # veritabanından tüm hareketleri ada göre sırala
    moves = Movement.query.order_by(Movement.name).all()
    return render_template("movements.html", movements=moves)
    
@app.route('/info')
def info():
    return render_template('info.html')    

# --------------------------------------
# Şifre Validasyonu
# --------------------------------------
def validate_password(pw):
    # En az 8 karakter, en az 1 BÜYÜK harf, 1 küçük harf, 1 rakam
    if len(pw) < 8:
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
        # ---------- Form verileri ----------
        username        = request.form.get("username")
        email           = request.form.get("email")
        password        = request.form.get("password")
        name            = request.form.get("name")
        zodiac          = request.form.get("zodiac")
        age_str         = request.form.get("age")
        city_id         = request.form.get("city")
        district_id     = request.form.get("district")

        gender          = request.form.get("gender")
        height_str      = request.form.get("height")
        weight_str      = request.form.get("weight")
        experience_level= request.form.get("experience_level")
        goals           = request.form.get("goals")

        chronic_conditions = get_checkbox_values("chronic_conditions_options")
        surgery_history    = request.form.get("surgery_history")
        drug_usage         = request.form.get("drug_usage")          # "evet" / "hayır"
        medications        = get_checkbox_values("drug_options") if drug_usage == "evet" else None
        supplement_usage   = get_checkbox_values("supplement_options")
        daily_water_intake = request.form.get("daily_water_intake")

        activity_level = request.form.get("activity_level")
        nutrition      = request.form.get("nutrition")

        # ---------- Basit doğrulamalar ----------
        if User.query.filter_by(username=username).first():
            flash("Bu kullanıcı adı zaten mevcut!")
            return render_template("register.html", cities=City.query.all())

        if not validate_password(password):
            flash("Şifre 8 karakter olmalı ve en az 1 büyük harf, 1 küçük harf, 1 rakam içermelidir.")
            return render_template("register.html", cities=City.query.all())

        # ---------- Sayısal doğrulamalar ----------
        errors = []

        # Yaş
        if age_str:
            try:
                age_val = int(age_str)
                if age_val <= 0:
                    errors.append("Yaş pozitif bir sayı olmalıdır.")
            except ValueError:
                errors.append("Yaş sayı olmalıdır.")
        else:
            age_val = None   # yaş alanını zorunlu tutmuyorsan

        # Boy
        if height_str:
            try:
                height_val = float(height_str)
                if height_val <= 0:
                    errors.append("Boy pozitif olmalıdır.")
            except ValueError:
                errors.append("Boy sayı olmalıdır.")
        else:
            height_val = None

        # Kilo
        if weight_str:
            try:
                weight_val = float(weight_str)
                if weight_val <= 0:
                    errors.append("Kilo pozitif olmalıdır.")
            except ValueError:
                errors.append("Kilo sayı olmalıdır.")
        else:
            weight_val = None

        # Hata varsa formu geri döndür
        if errors:
            for msg in errors:
                flash(msg)
            return render_template("register.html", cities=City.query.all())


        # ---------- Nesneleri oluştur ----------
        hashed_pw = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_pw
        )

        new_profile = UserProfile(
            user=new_user,                 # ilişkiyi böyle kurmak daha temiz
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

        # ---------- Tek transaction ----------
        try:
            db.session.add_all([new_user, new_profile])
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Bu kullanıcı adı veya e‑posta zaten kayıtlı!")
            return render_template("register.html", cities=City.query.all())

        # ---------- Oturumu aç & yönlendir ----------
        session["user_id"]  = new_user.id
        session["username"] = new_user.username
        flash("Kayıt başarılı, hoş geldiniz!")
        return redirect(url_for("sports"))

    # ------------- GET: formu göster -------------
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
# Öneri motoru: <50 puan → eski mantık, aksi hâlde ML sıralama
# --------------------------------------
def recommend_for_user(user, limit=6):
    """Veri azsa basit, yeterliyse ML tabanlı öneri döndürür."""
    # ----- FALLBACK KOŞULU -----
    if UserProgramRating.query.count() < 50 or pipeline is None:
        auto_gender = user.profile.gender or "unisex"
        auto_level  = (user.profile.experience_level or "").lower()

        q = (
            db.session.query(Program, func.avg(UserProgramRating.rating).label("avg_r"))
            .outerjoin(UserProgramRating, Program.id == UserProgramRating.program_id)
            .filter((Program.gender == auto_gender) | (Program.gender == "unisex"))
            .group_by(Program.id)
        )
        if auto_level:
            q = q.filter(func.lower(Program.level) == auto_level)

        return [p for p, _ in q.order_by(func.avg(UserProgramRating.rating).desc()).limit(limit)]

    # ----- ML SIRALAMA -----
    candidates = Program.query.all()
    scored = [(p, predict_score(user, p)) for p in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:limit]]

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

    # ——— yeni GET parametreleri ———
    days  = request.args.get("days")      # "1" | "3" | "5"
    focus = request.args.get("focus")     # "Full Body" | "Hybrid"

    # ——— temel sorgu: cinsiyet & seviye filtresi ———
    auto_gender = user.profile.gender or "unisex"
    auto_level  = (user.profile.experience_level or "").lower()
    query = Program.query.filter(
        (Program.gender == auto_gender) | (Program.gender == "unisex")
    )
    if auto_level:
        query = query.filter(func.lower(Program.level) == auto_level)

    # ——— yeni filtreler: gün sayısı & odak ———
    if days:
        query = query.filter(Program.days_per_week == int(days))
    if focus:
        query = query.filter(Program.focus_area == focus)

    # ——— program listesini al ———
    programs = query.order_by(Program.level, Program.name).all()

    # — ÖNERİLENLER —
    recommended_programs = recommend_for_user(user)
    # — Filtreleri önerilen programlara da uygula —
    if days:
        recommended_programs = [
            p for p in recommended_programs
            if p.days_per_week == int(days)
        ]
    if focus:
        recommended_programs = [
            p for p in recommended_programs
            if p.focus_area == focus
        ]
    recommended_ids = {p.id for p in recommended_programs}
    programs = [p for p in programs if p.id not in recommended_ids]

    # ---------- METRİK SORGUSU ----------
    all_ids = recommended_ids.union({p.id for p in programs})
    metrics = {}
    if all_ids:
        rows = (
            db.session.query(
                UserProgramRating.program_id.label("pid"),
                func.avg(UserProgramRating.rating).label("avg"),
                func.count(UserProgramRating.id).label("cnt"),
                func.avg(UserProgramRating.duration).label("avg_dur"),
                func.sum(
                    case((UserProgramRating.progress >= 80, 1), else_=0)
                ).label("completed")
            )
            .filter(UserProgramRating.program_id.in_(all_ids))
            .group_by(UserProgramRating.program_id)
            .all()
        )
        metrics = {
            r.pid: {
                "avg": round(float(r.avg or 0), 1),
                "cnt": r.cnt,
                "avg_dur": round(float(r.avg_dur or 0), 1),
                "comp_pct": round((r.completed / r.cnt * 100) if r.cnt else 0)
            }
            for r in rows
        }

    # ——— 2. adım: başlanan ve puanlanan program ID’leri ———
    started_ids = {up.program_id for up in user.user_programs}
 # ——— 2. adım: başlanan ve puanlanan program ID’leri ———
# Kullanıcı puan verdiği programlar:
    rated_ids = {
        upr.program_id
        for upr in UserProgramRating.query.filter_by(user_id=user_id).all()
    }
    modal_cfg = session.pop("next_step_modal", None)

    return render_template(
        "sports.html",
        programs=programs,
        recommended_programs=recommended_programs,
        metrics=metrics,
        modal_cfg=modal_cfg,
        started_ids=started_ids,
        rated_ids=rated_ids
    )

# --------------------------------------
# KULLANICININ SEÇTİĞİ PROGRAMI İŞLEME (CHOOSE PROGRAM)
# --------------------------------------
from datetime import date  # dosyanın en üstünde ekleyin

@app.route("/choose_program/<int:program_id>")
def choose_program(program_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Önce giriş yapmanız gerekir!")
        return redirect(url_for("login"))

    # Program var mı kontrol et (404 döndürürse sports'a yönlendirirsiniz)
    program = Program.query.get_or_404(program_id)

    # Eğer daha önce başlamamışsa, user_programs tablosuna kaydet
    existing = UserProgram.query.filter_by(
        user_id=user_id, program_id=program_id
    ).first()
    if not existing:
        new_up = UserProgram(
            user_id=user_id,
            program_id=program_id,
            start_date=date.today(),
            progress=0,
            status="active"
        )
        db.session.add(new_up)
        db.session.commit()
        flash("Program başlatıldı! İstediğiniz zaman bitirip puanlayabilirsiniz.")
    else:
        flash("Bu programı zaten başlatmışsınız.")

    # Artık rate_program'a değil, doğrudan sports sayfasına dönüyoruz
    return redirect(url_for("sports"))
# --------------------------------------
# 2) HELPER FONKSİYONLAR
# --------------------------------------
def program_stats(program_id):
    """Her program için ortalama puan ve oy sayısını döner."""
    avg_rating, num_ratings = (
        db.session.query(
            func.coalesce(func.avg(UserProgramRating.rating), 0),
            func.count(UserProgramRating.id)
        )
        .filter(UserProgramRating.program_id == program_id)
        .first()
    )
    return float(avg_rating), int(num_ratings)

app.jinja_env.globals['program_stats'] = program_stats
# --------------------------------------
# Program için ortalama puan & toplam oy
# --------------------------------------

def program_metrics(program_id):
    # Ortalama kullanım süresi (dakika)
    avg_duration = (
        db.session.query(func.coalesce(func.avg(UserProgramRating.duration), 0))
        .filter(UserProgramRating.program_id == program_id)
        .scalar()
    )
    avg_duration = round(avg_duration, 1)
    
    # Toplam puan sayısı
    total = (
        db.session.query(func.count(UserProgramRating.id))
        .filter(UserProgramRating.program_id == program_id)
        .scalar()
    ) or 0

    # >= %80 ilerleme yapan sayısı
    completed = (
        db.session.query(func.count(UserProgramRating.id))
        .filter(
            UserProgramRating.program_id == program_id,
            UserProgramRating.progress >= 80
        )
        .scalar()
    ) or 0

    # Tamamlama oranı %
    comp_pct = round((completed / total * 100), 0) if total else 0

    return avg_duration, int(comp_pct)

# Jinja’ya global olarak ekleyin
app.jinja_env.globals['program_metrics'] = program_metrics

# --------------------------------------
# PROGRAMI PUANLAMA (RATE PROGRAM)
# --------------------------------------
@app.route("/rate_program/<int:program_id>", methods=["GET", "POST"])
def rate_program(program_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Önce giriş yapmanız gerekir!")
        return redirect(url_for("login"))

    # Normal GET / POST akışı
    program = Program.query.get_or_404(program_id)

    if request.method == "POST":
        # --- 1. Form değerlerini al ---
        rating_val   = request.form.get("rating", "0")
        duration_val = request.form.get("duration", "")
        progress_val = request.form.get("progress", "")

        # --- 2. Temel doğrulamalar ---
        try:
            rating = int(rating_val)
            if rating not in range(1, 6):
                raise ValueError
        except ValueError:
            flash("Puan 1-5 arasında olmalı.")
            return redirect(request.url)

        try:
            duration = int(duration_val) if duration_val else None
            if duration is not None and not 1 <= duration <= 600:
                raise ValueError
        except ValueError:
            flash("Kullanım süresi 1-600 dakika arasında olmalı.")
            return redirect(request.url)

        try:
            progress = float(progress_val) if progress_val else None
            if progress is not None and not 0 <= progress <= 100:
                raise ValueError
        except ValueError:
            flash("İlerleme %0-100 arasında olmalı.")
            return redirect(request.url)

        # --- 3. Daha önce puanlanmış mı kontrolü ---
        existing = UserProgramRating.query.filter_by(
            user_id=user_id,
            program_id=program_id
        ).first()

        if existing:
            # Var olan kaydı güncelle
            existing.rating   = rating
            existing.duration = duration
            existing.progress = progress
            db.session.commit()
            flash("Bu programı daha önce puanladınız, puanınız güncellendi!")
        else:
            # Yeni kayıt ekle
            new_rating = UserProgramRating(
                user_id    = user_id,
                program_id = program_id,
                rating     = rating,
                duration   = duration,
                progress   = progress
            )
            db.session.add(new_rating)
            db.session.commit()
            flash("Puanınız kaydedildi, teşekkürler!")

        # --- 4. İleri seviye / kolay modal kontrolü ---
        if rating >= 4 and (progress or 0) >= 70:
            session["next_step_modal"] = {
                "title":  "Tebrikler!",
                "body":   "Bu programı neredeyse tamamladınız. İleri seviye bir programa geçmek ister misiniz?",
                "btn_txt": "İleri Seviye Programları Göster",
                "btn_url": url_for("sports", show_all="true")
            }
        elif rating <= 2:
            session["next_step_modal"] = {
                "title":  "Zor mu geldi?",
                "body":   "Sizin için daha kolay programlar seçtik.",
                "btn_txt": "Daha Kolay Programları Gör",
                "btn_url": url_for("sports", show_all="true")
            }

        return redirect(url_for("sports"))

    # GET isteğinde formu göster
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

    # 1) Toplam başlanan program sayısı
    total_started = UserProgram.query.filter_by(user_id=user_id).count()

    # 2) Toplam puan verilen program sayısı
    total_rated  = UserProgramRating.query.filter_by(user_id=user_id).count()

    # 3) Ortalama puan (2 ondalık)
    avg_rating = db.session.query(
        func.coalesce(func.avg(UserProgramRating.rating), 0)
    ).filter_by(user_id=user_id).scalar()
    avg_rating = round(avg_rating, 2)

    # 4) Puan dağılımı için etiketler ve sayılar
    rating_labels = ["1", "2", "3", "4", "5"]
    rating_data   = [
        UserProgramRating.query.filter_by(user_id=user_id, rating=int(lbl)).count()
        for lbl in rating_labels
    ]

    return render_template(
        "profile.html",
        user=user,
        profile=user.profile,
        total_started=total_started,
        total_rated=total_rated,
        avg_rating=avg_rating,
        rating_labels=rating_labels,
        rating_data=rating_data
    )
# --------------------------------------
# UYGULAMAYI BAŞLAT
# --------------------------------------
if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)

