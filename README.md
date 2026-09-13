# Rezervia

Flask + SQLAlchemy + SQLite ile hazırlanmış rezervasyon uygulaması.

## Windows kurulumu

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python create_admin.py
python app.py
```

Tarayıcı: http://127.0.0.1:5000

İlk admin hesabını `create_admin.py` ile oluşturun. Veritabanı ilk çalıştırmada `instance/reservation.db` altında oluşur.
