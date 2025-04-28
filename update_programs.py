# -*- coding: utf-8 -*-
"""
NULL meta alanlarını Excel'den doldurur.
pprograms_enriched.xlsx dosyasını bu betikle aynı klasöre koyun.
Çalıştır:  python fill_null_meta_from_excel.py
"""

import pandas as pd
from pathlib import Path
from app import app, db, Program

# ---------------- 1) Excel'i oku ----------------
BASE_DIR = Path(__file__).parent
excel_path = BASE_DIR / "pprograms_enriched.xlsx"
if not excel_path.exists():
    raise FileNotFoundError(f"Excel bulunamadı: {excel_path}")

df = pd.read_excel(excel_path)

# ---------------- 2) DB güncelle ----------------
updated_rows = 0

with app.app_context():
    for _, row in df.iterrows():
        prog = Program.query.filter_by(name=row["name"]).first()
        if not prog:
            continue  # Excel'de olup DB'de olmayan satır — atla

        # Her alan için: eğer DB'de NULL ise Excel'deki değeri yaz
        if prog.days_per_week is None and not pd.isna(row.get("days_per_week")):
            prog.days_per_week = int(row["days_per_week"])
        if not prog.focus_area and isinstance(row.get("focus_area"), str):
            prog.focus_area = row["focus_area"]
        if not prog.program_group and isinstance(row.get("program_group"), str):
            prog.program_group = row["program_group"]
        if getattr(prog, "weeks_total", None) is None and "weeks_total" in row and not pd.isna(row["weeks_total"]):
            prog.weeks_total = int(row["weeks_total"])

        updated_rows += 1

    db.session.commit()

print(f"✅ Güncellendi (NULL → değer yazılan satır sayısı): {updated_rows}")
