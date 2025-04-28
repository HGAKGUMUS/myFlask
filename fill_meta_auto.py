# -*- coding: utf-8 -*-
"""
program_group ve weeks_total alanlarını otomatik türetip günceller.
Çalıştır: python fill_meta_auto.py

 - program_group için program adının ilk iki kelimesini alır.
 - weeks_total için ad içinde '3 hafta', '4 haftalık' vb. ifadelerden sayıyı çeker; bulamazsa 1.
"""

import re
import pandas as pd
from app import app, db, Program

def infer_group(name: str) -> str:
    parts = name.split()
    return " ".join(parts[:2])

def infer_weeks(name: str) -> int:
    m = re.search(r'(\d+)\s*hafta', name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1

def main():
    # Excel dosyanızın adı (aynı klasörde)
    df = pd.read_excel("pprograms_enriched.xlsx")

    with app.app_context():
        updated = 0
        for _, row in df.iterrows():
            prog = Program.query.filter_by(name=row["name"]).first()
            if not prog:
                continue

            pg_val = infer_group(prog.name)
            wt_val = infer_weeks(prog.name)

            changed = False
            if prog.program_group != pg_val:
                prog.program_group = pg_val
                changed = True
            if prog.weeks_total != wt_val:
                prog.weeks_total = wt_val
                changed = True

            if changed:
                updated += 1

        db.session.commit()
    print(f"✅ Güncellenen program sayısı: {updated}")

if __name__ == "__main__":
    main()
