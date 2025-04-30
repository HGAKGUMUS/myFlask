# seed_movements.py
import re
from app import app, db
from app import Program, Movement  # Eğer Movement modelini ayrı bir dosyada tanımladıysan doğru import yolunu kullan

with app.app_context():
    # 1) Önce eski hareketleri temizle (opsiyonel)
    Movement.query.delete()
    db.session.commit()

    seen = set()
    count = 0

    # 2) Tüm programları dolaş
    for p in Program.query:
        steps = p.exercise_steps or ""
        # "1. Squat; 2. Push-Up" → ["Squat","Push-Up"]
        parts = [re.sub(r"^\d+\.\s*", "", s).strip()
                 for s in steps.split(";") if s.strip()]
        for name in parts:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                m = Movement(name=name)
                db.session.add(m)
                count += 1

    # 3) Commit et
    db.session.commit()
    print(f"✅ {count} adet tekil hareket eklendi.")
