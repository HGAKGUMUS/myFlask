# update_notes_db.py

import os
import sys

"""
Veritabanındaki Program kayıtlarını okuyup `notes` alanını günceller.
Protein, su, karbonhidrat ve ısınma/soğuma tavsiyelerini seviye ve cinsiyete göre dinamik yazdırır.

Kullanım:
1. Bu dosyayı proje kök dizinine (`app.py` ile aynı dizine) kaydedin.
2. Sanal ortamı aktifleştirin:
   Windows: .venv\Scripts\activate
   macOS/Linux: source .venv/bin/activate
3. python update_notes_db.py
"""

# Proje kökünü PYTHONPATH'e ekleyin
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import app, db, Program

# Protein katsayıları (g/kg) seviye ve cinsiyete göre sabit
PROTEIN_MULTIPLIERS = {
    'female': {
        'Beginner': 1.2,
        'Intermediate': 1.4,
        'Advanced': 1.6
    },
    'male': {
        'Beginner': 1.3,
        'Intermediate': 1.5,
        'Advanced': 1.7
    }
}

# Su öneri (L) seviye bazlı minimum değerler
WATER_BASE = {
    'Beginner': 2.0,
    'Intermediate': 2.5,
    'Advanced': 3.0
}

# Karbonhidrat öneri cümlesi
CARB_SENTENCE = (
    "Yüksek lifli tam tahıllar (esmer pirinç, yulaf), baklagiller ve taze sebzeler gibi "
    "sağlıklı karbonhidrat kaynaklarını tercih edin."
)

# Isınma / soğuma cümlesi
WARM_COOL = (
    "Antrenman öncesi 10 dakika dinamik ısınma, sonrası ise 10 dakika esneme yapın."
)

# Aktif dinlenme cümlesi
ACTIVE_RECOVERY = (
    "Her hafta bir gün aktif dinlenme (örneğin yürüyüş veya yoga) yaparak toparlanmanızı hızlandırın."
)


def generate_notes(prog):
    """Program meta verilerine göre detaylı not oluşturur."""
    # Meta veriler
    days = prog.days_per_week or 1
    weeks = prog.weeks_total or 1
    focus = (prog.focus_area or "").lower()
    diff = prog.difficulty or 1
    level = prog.level or 'Beginner'
    gender = getattr(prog, 'gender', 'male').lower()

    # 1) Kas grupları
    if "full body" in focus or days == 1:
        muscles = "göğüs, sırt, bacak, omuz ve karın kasları"
    elif "split" in focus or days == 3:
        muscles = "üst gövde, alt gövde ve karın kasları"
    elif "hybrid" in focus:
        muscles = "dayanıklılık ve kuvvet kas grupları"
    else:
        muscles = "ana kas grupları"

    # 2) Set arası dinlenme süresi
    if days == 5:
        rest = "45-60 saniye"
    elif days == 3:
        rest = "60-90 saniye"
    else:
        rest = "60-120 saniye"

    # 3) Günlük su ihtiyacı (litre) – seviye bazlı minimum
    base_water = WATER_BASE.get(level, 2.0)
    calc_water = round(2 + 0.5 * max(0, weeks - 1), 1)
    water = max(calc_water, base_water)

    # 4) Protein tavsiyesi – çarpma oranını sabit göster
    multiplier = PROTEIN_MULTIPLIERS.get(gender, PROTEIN_MULTIPLIERS['male']).get(level, 1.3)
    protein_sentence = (
        f"Protein ihtiyacınızı hesaplamak için kilonuzla {multiplier:.1f} g/kg oranını çarpın; "
        "örneğin 70 kg × {multiplier:.1f} g = 98 g protein. "
        "Antrenman sonrası whey proteini veya tavuk eti gibi kaliteli bir kaynak kullanabilirsiniz."
    )

    # Not cümleleri
    sentences = [
        f"Bu programda {muscles} üzerinde çalışacaksınız.",
        f"Her set arasında yaklaşık {rest} dinlenme yapın.",
        WARM_COOL,
        f"Program toplam {weeks} hafta sürecek; ilerlemenizi her hafta not edin.",
        f"Günde en az {water} L su tüketmeye özen gösterin.",
        protein_sentence,
        CARB_SENTENCE,
        ACTIVE_RECOVERY
    ]

    return " ".join(sentences)


def main():
    with app.app_context():
        updated = 0
        for prog in Program.query.all():
            new_note = generate_notes(prog)
            if prog.notes != new_note:
                prog.notes = new_note
                updated += 1
        db.session.commit()
        print(f"✅ Güncellenen program sayısı: {updated}")


if __name__ == "__main__":
    main()
