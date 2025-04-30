# seed_program_notes.py
# Program.notes alanını seviye, type ve focus_area kombinasyonlarına göre özelleştirme örneği
from app import app, db
from app import Program, Category

# Ortak uyarı metni
note_common = "Doğru formu koruyun."

# experience_level, type ve focus_area'a göre ek açıklamaları belirleyen fonksiyon
def get_extra_notes(level, ptype, focus):
    notes = []
    # 1) Isınma & Soğuma Vurgusu
    if level == "Beginner" and ptype == "Kardiyo":
        notes.append("Antrenmandan önce mutlaka 5 dk hafif tempo koşu ile ısının.")
        notes.append("Hareket geçişlerinde nefes kontrolüne odaklanın.")
    if level == "Intermediate" and ptype == "Fitness":
        notes.append("Set aralarında 60 sn kadar aktif dinlenme (hafif germe) yapın, kaslarınızın soğumasına izin verin.")
    if level == "Advanced" and focus in ["Split", "Hybrid"]:
        notes.append("Her blok sonunda 2 dk bekleyerek kas grubunuza odaklanın; aşırı yığılma riskine dikkat edin.")

    # 2) Teknik & Form İpuçları
    if level == "Beginner" and ptype == "Fitness" and focus == "Full Body":
        notes.append("Squat yaparken dizlerinizin ayak parmaklarınızla aynı hizada olmasına dikkat edin.")
    if level == "Intermediate" and ptype == "Fitness":
        notes.append("Dumbbell bench press’te göğüs kaslarını kasın; omuzları sıkıştırmayın.")
    if level == "Advanced":
        notes.append("Her tekrarın sonunda core (karın) bölgesini sıkı tutun, bel hizasını koruyun.")

    # 3) Nefes & Tempo
    if ptype == "Kardiyo" and focus == "Full Body":
        notes.append("Ritimli nefes alıp verin; 2 adım nefes, 2 adım nefes ver şeklinde tempo tutun.")
    if ptype == "Fitness":
        notes.append("Hareketin zor kısmında nefes verin, dönüş kısmında nefes alın.")
    if ptype == "Yoga":
        notes.append("Her pozu 3 nefes boyunca sabitleyin; omurganızı dik tutmaya odaklanın.")

    # 4) Odak Bölgesi & Hedefe Yönelik Mesaj
    if focus == "Split" and ptype == "Fitness":
        notes.append("Sırt kaslarınızı hissettiğinizden emin olun; kürek kemiklerinizi birbirine doğru çekin.")
        notes.append("Karın kaslarınızı soluk borusuna doğru çekerek sabitleyin, squat’ta dizleri içe düşürmeyin.")
    if focus == "Hybrid":
        notes.append("Her setin yarısında patlayıcı hareket (burpee/jump squat) ekleyerek kondisyonu artırın.")

    # 5) Motivasyon & İlerleme
    if level == "Beginner":
        notes.append("Harika başladınız! Her gün ilerlemenizi kaydedin; 1 hafta sonra tekrar değerlendirin.")
    if level == "Intermediate":
        notes.append("Kendi rekorunuzu kırmayı hedefleyin; önceki max tekrar sayınızı aşmaya çalışın.")
    if level == "Advanced":
        notes.append("Ağırlığı %5 artırarak yeni plateau’lar keşfedin; aşamalı zorluk için yeni setler ekleyin.")

    return " ".join(notes)

with app.app_context():
    # Category objesini çek
    category = Category.query.filter_by(name="Fitness").first()

    # Örnek: "Beginner Full Body (Erkek)" programını düzenleme veya ekleme
    program = Program.query.filter_by(name="Beginner Full Body (Erkek)").first()
    if not program:
        program = Program(
            name="Beginner Full Body (Erkek)",
            category_id=category.id,
            level="Beginner",
            exercise_steps="1. Isınma; 2. Ana Egzersiz; 3. Soğuma",
            duration=30,
            rest_intervals="Set arası 1 dk",
            gender="male",
            difficulty=1,
            type="Fitness",
            days_per_week=3,
            focus_area="Full Body",
            weeks_total=4
        )
        db.session.add(program)

    # notes alanını güncelle (eski metni silmeden ekler)
    extra = get_extra_notes(program.level, program.type, program.focus_area)
    if extra not in (program.notes or ""):
        program.notes = (program.notes or note_common) + " " + extra
        db.session.commit()
        print("✅ 'Beginner Full Body (Erkek)' programının notes alanı güncellendi.")
    else:
        print("ℹ️ Notes zaten güncel, tekrar eklenmedi.")
