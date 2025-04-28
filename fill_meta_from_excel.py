# -*- coding: utf-8 -*-
"""
Program.meta alanlarını Excel verisinden güncelleyip doldurur:
- program_group
- weeks_total

Kullanım: python fill_meta_from_excel.py
"""

import pandas as pd
from app import app, db, Program

def main():
    # Excel dosyasını okuyun
    df = pd.read_excel("pprograms_enriched.xlsx")
    
    with app.app_context():
        updated = 0
        for _, row in df.iterrows():
            name = row.get("name")
            # Programı DB'den çek
            prog = Program.query.filter_by(name=name).first()
            if not prog:
                continue
            
            # Excel sütunlarından değer al
            pg = row.get("program_group")
            wt = row.get("weeks_total")
            
            # weeks_total NaN olabilir; int yapın
            wt_val = int(wt) if pd.notna(wt) else None
            
            # Fark edenleri güncelle
            if prog.program_group != pg or prog.weeks_total != wt_val:
                prog.program_group = pg
                prog.weeks_total   = wt_val
                updated += 1
        
        db.session.commit()
        print(f"✅ Güncellenen program sayısı: {updated}")

if __name__ == "__main__":
    main()
