# synthetic_test_data.py
# Bu script test amaçlı 20-30 civarı sentetik rating verisi oluşturur.
# Proje kök dizininde çalıştırın: python synthetic_test_data.py

import random
from werkzeug.security import generate_password_hash
from app import app, db, User, UserProfile, Program, UserProgramRating

with app.app_context():
    synthetic_users = []
    levels = ['Beginner', 'Intermediate', 'Advanced']
    # 1) Test kullanıcıları oluştur
    for lvl in levels:
        for i in range(3):  # Her seviyeden 3 kullanıcı
            username = f"test_{lvl.lower()}_{i}"
            email = f"{username}@example.com"
            pw_hash = generate_password_hash("Test1234")
            user = User(username=username, email=email, password=pw_hash)
            db.session.add(user)
            db.session.flush()
            # Profil
            profile = UserProfile(
                user_id=user.id,
                name=f"Test {lvl} {i}",
                age=random.randint(18, 60),
                gender=random.choice(['male', 'female']),
                height=round(random.uniform(150, 190), 1),
                weight=round(random.uniform(50, 100), 1),
                experience_level=lvl,
                city_id=None,
                district_id=None
            )
            db.session.add(profile)
            synthetic_users.append(user)
    db.session.commit()

    # 2) Sentetik ratingler ekle
    for user in synthetic_users:
        # Kullanıcının seviyesindeki programları seç
        progs = Program.query.filter_by(level=user.profile.experience_level).all()
        sample = random.sample(progs, min(5, len(progs)))
        for prog in sample:
            rating = random.randint(1, 5)
            duration = random.randint(max(1, prog.duration - 5), prog.duration + 5)
            progress = round(random.uniform(50, 100), 1)
            upr = UserProgramRating(
                user_id=user.id,
                program_id=prog.id,
                rating=rating,
                duration=duration,
                progress=progress
            )
            db.session.add(upr)
    db.session.commit()

    print(f"✅ Sentetik test verisi eklendi: {len(synthetic_users)} kullanıcı, toplam ~{len(synthetic_users)*5} rating")
