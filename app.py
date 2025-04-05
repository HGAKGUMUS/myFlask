# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "mysecretkey"

# PostgreSQL bağlantınızı buraya göre ayarlayın:
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:postgres@localhost:5432/fitboost_db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------------------------------------------------
# MODELLER (Tablolar)
# -------------------------------------------------------------------

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    gender = db.Column(db.String(20))
    experience_level = db.Column(db.String(20))
    # İsterseniz boy, kilo vb. alanlar ekleyebilirsiniz

class Program(db.Model):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(50))
    gender = db.Column(db.String(20))
    exercise_steps = db.Column(db.Text)

class UserProgram(db.Model):
    __tablename__ = 'user_programs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)

from sqlalchemy import UniqueConstraint

class UserProgramRating(db.Model):
    """
    (user_id, program_id) çifti için tek bir rating tutmak üzere unique kısıt kullanıyoruz.
    """
    __tablename__ = 'user_program_ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 arası puan
    feedback = db.Column(db.Text)                   # opsiyonel yorum
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'program_id', name='unique_user_program'),
    )

# -------------------------------------------------------------------
# ROUTE'LAR
# -------------------------------------------------------------------

@app.route('/')
def home():
    """
    Ana sayfa: Kullanıcı giriş yaptıysa user_id session'da bulunur.
    """
    user_id = session.get('user_id')
    user = None
    if user_id:
        user = User.query.get(user_id)
    return render_template('home.html', user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Kayıt: Kullanıcı adı, email, şifre, cinsiyet, deneyim seviyesi gibi bilgileri alıp kaydeder.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        gender = request.form.get('gender')
        experience_level = request.form.get('experience_level')

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash("Bu kullanıcı adı veya e-posta zaten kayıtlı!")
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()

        new_profile = UserProfile(
            user_id=new_user.id,
            gender=gender,
            experience_level=experience_level
        )
        db.session.add(new_profile)
        db.session.commit()

        session['user_id'] = new_user.id
        flash("Kayıt işlemi tamamlandı, hoş geldiniz!")
        return redirect(url_for('home'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Giriş: Kullanıcı adı ve şifre kontrolü yaparak session'a user_id atar.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash("Başarıyla giriş yaptınız.")
            return redirect(url_for('home'))
        else:
            flash("Kullanıcı adı veya şifre hatalı.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Çıkış: Session'dan user_id silinir.
    """
    session.pop('user_id', None)
    flash("Çıkış yaptınız.")
    return redirect(url_for('home'))

@app.route('/sports')
def sports():
    """
    Spor Programlarını Listele: Tüm programları görüntüler.
    """
    programs = Program.query.all()
    return render_template('sports.html', programs=programs)

@app.route('/choose_program/<int:program_id>', methods=['GET', 'POST'])
def choose_program(program_id):
    """
    Kullanıcının bir programı seçtiğini (UserProgram) kaydeder.
    """
    user_id = session.get('user_id')
    if not user_id:
        flash("Program seçmek için giriş yapmalısınız.")
        return redirect(url_for('login'))

    program = Program.query.get_or_404(program_id)
    already_chosen = UserProgram.query.filter_by(user_id=user_id, program_id=program_id).first()
    if already_chosen:
        flash("Bu programı zaten seçmişsiniz.")
    else:
        new_user_program = UserProgram(user_id=user_id, program_id=program_id)
        db.session.add(new_user_program)
        db.session.commit()
        flash("Program başarıyla seçildi.")
    return redirect(url_for('sports'))

@app.route('/rate_program/<int:program_id>', methods=['GET', 'POST'])
def rate_program(program_id):
    """
    Tek kayıt mantığı: (user_id, program_id) için zaten kayıt varsa günceller, yoksa ekler.
    """
    user_id = session.get('user_id')
    if not user_id:
        flash("Puanlama yapmak için giriş yapmalısınız.")
        return redirect(url_for('login'))

    program = Program.query.get_or_404(program_id)

    if request.method == 'POST':
        rating_val = int(request.form.get('rating', 0))
        feedback_txt = request.form.get('feedback', '')

        existing_rating = UserProgramRating.query.filter_by(user_id=user_id, program_id=program_id).first()
        if existing_rating:
            existing_rating.rating = rating_val
            existing_rating.feedback = feedback_txt
            existing_rating.timestamp = datetime.utcnow()
        else:
            new_rating = UserProgramRating(
                user_id=user_id,
                program_id=program_id,
                rating=rating_val,
                feedback=feedback_txt
            )
            db.session.add(new_rating)

        try:
            db.session.commit()
            flash("Teşekkürler, geri bildiriminiz kaydedildi!")
        except Exception as e:
            db.session.rollback()
            flash(f"Bir hata oluştu: {e}")

        return redirect(url_for('sports'))

    return render_template('rate_program.html', program=program)

@app.route('/profile')
def profile():
    """
    Kullanıcının temel bilgilerini ve seçtiği programları gösterir.
    """
    user_id = session.get('user_id')
    if not user_id:
        flash("Profilinizi görüntülemek için giriş yapmalısınız.")
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)
    user_profile = UserProfile.query.filter_by(user_id=user_id).first()
    user_programs = UserProgram.query.filter_by(user_id=user_id).all()

    return render_template('profile.html', user=user, user_profile=user_profile, user_programs=user_programs)


# -------------------------------------------------------------------
# UYGULAMAYI ÇALIŞTIRMA
# -------------------------------------------------------------------
if __name__ == '__main__':
    # Geliştirme sırasında tabloları sıfırlamak isterseniz (dikkat! verileriniz silinir):
    #
    # with app.app_context():
    #     db.drop_all()
    #     db.create_all()
    #     print("Veritabanı tabloları sıfırlandı ve yeniden oluşturuldu.")
    #
    app.run(debug=True)
