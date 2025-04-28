# -*- coding: utf-8 -*-
"""
Program.notes alanlarını her programa özgü, farklı ipuçlarıyla günceller.
Çalıştır: python update_program_notes.py
"""

import random
from app import app, db, Program

def generate_notes(prog):
    """
    days_per_week, type ve program_group bilgilerine göre
    her programa farklı 7-8 cümlelik not metni oluşturur.
    """
    d     = prog.days_per_week or 1
    t     = prog.type or "Antrenman"
    grp   = prog.program_group or ""
    lvl   = prog.level or ""
    
    # Başlangıç mesajları (days_per_week bazlı)
    start_msgs = {
        1: [
            f"Bu tek günlük {t} rutini tüm kas gruplarını yoğun çalıştırır.",
            "Denge ve form odaklı ilerleyin, sakatlanmaları önleyin."
        ],
        3: [
            f"Bu 3 günlük {t} programı üst-alt gövde ve karın odaklı seanslar sunar.",
            "Her günü farklı kas grubuna odaklanarak geçirin."
        ],
        5: [
            f"Haftalık 5 günlük {t} planı kas dayanıklılığını artırmak için ideal.",
            "Her gün hafif-orta yoğunlukta tam vücut çalışması yapın."
        ],
    }
    
    # Genel ipuçları havuzu
    tips = [
        "Her set arasında 60-90 saniye dinlenin.",
        "Antrenman öncesi 10 dakikalık dinamik ısınma yapın.",
        "Antrenman sonrası esneme ile kasları rahatlatın.",
        "20 dakikada bir 200 ml su tüketmeyi unutmayın.",
        "Antrenman sonrası 20–30 g protein alın (whey veya tavuk).",
        "Günlük su tüketiminizi 2–3 litre arası tutun.",
        "Haftada bir gün aktif dinlenme (yürüyüş, yoga) yapın."
    ]
    
    parts = []
    # 1) Gün sayısına özel satır
    parts.append(random.choice(start_msgs[d]))
    # 2) Grup vurgusu
    if grp:
        parts.append(f"Program grubu: {grp}, rutininize kolayca entegre edilir.")
    # 3) Seviye vurgusu
    if lvl:
        parts.append(f"{lvl} seviyeye uygun zorlukta setler içerir.")
    # 4) İki rastgele ipucu
    parts.extend(random.sample(tips, 2))
    
    # Metni birleştir
    return " ".join(parts)

if __name__ == "__main__":
    with app.app_context():
        updated = 0
        for prog in Program.query.all():
            new_note = generate_notes(prog)
            if prog.notes != new_note:
                prog.notes = new_note
                updated += 1
        db.session.commit()
    print(f"✅ Güncellenen program sayısı: {updated}")
