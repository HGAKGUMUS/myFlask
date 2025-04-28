# -*- coding: utf-8 -*-
"""
Program meta alanlarını (days_per_week, focus_area) otomatik doldurur / düzeltir.
Çalıştır:  python fill_days_focus.py
"""

import re
from app import app, db, Program

# ---------- Yardımcı kural ----------
def infer_days(name: str) -> int:
    """
    • 'Split A'  → 3
    • 'Day1' .. 'Day5' → 5
    • diğerleri → 1
    """
    if re.search(r'Split\s*A', name, re.I):
        return 3
    if re.search(r'Day\s*[1-5]', name, re.I):
        return 5
    return 1

updated = 0

with app.app_context():
    for prog in Program.query.all():
        d = infer_days(prog.name)
        f = "Full Body" if d == 1 else "Hybrid"

        # Yalnızca bir şey değişirse yaz
        if prog.days_per_week != d or prog.focus_area != f:
            prog.days_per_week = d
            prog.focus_area   = f
            updated += 1

    db.session.commit()

print(f"✅ Güncellenen satır sayısı: {updated}")
