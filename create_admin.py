from getpass import getpass

from app import app, db
from app import User


with app.app_context():
    db.create_all()
    print("Yeni admin hesabı oluştur")
    username = input("Admin").strip()
    email = input("newscreaht@gmail.com: ").strip().lower()
    password = getpass("Admin")

    if not username or not email or not password:
        raise SystemExit("Tüm alanlar zorunludur.")
    if User.query.filter((User.username == username) | (User.email == email)).first():
        raise SystemExit("Bu kullanıcı adı veya e-posta zaten kayıtlı.")

    admin = User(username=username, email=email, first_name="Site", last_name="Yöneticisi", is_admin=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print("Admin hesabı başarıyla oluşturuldu.")
