from app import app, create_tables

with app.app_context():
    create_tables()
    print("Tablolar başarıyla oluşturuldu!")
