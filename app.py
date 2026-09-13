from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
import os
import re
from uuid import uuid4

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_wtf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reservations = db.relationship("Reservation", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    base_price = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    per_person_price = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    per_day_price = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    unit = db.Column(db.String(40), default="Hizmet")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    reservations = db.relationship("Reservation", backref="service", lazy=True)


class PricingRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class PricingSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(80), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)


class BlockedDate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(255), default="")


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_no = db.Column(db.String(40), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    people_count = db.Column(db.Integer, default=1, nullable=False)
    room_count = db.Column(db.Integer, default=0, nullable=False)
    vehicle_count = db.Column(db.Integer, default=0, nullable=False)
    led_area = db.Column(db.Integer, default=0, nullable=False)
    light_count = db.Column(db.Integer, default=0, nullable=False)
    extra_services = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    estimated_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    admin_note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("ReservationItem", backref="reservation", lazy=True, cascade="all, delete-orphan")


class ReservationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservation.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


STATUS_LABELS = {"pending": "Beklemede", "approved": "Onaylandı", "rejected": "Reddedildi", "cancelled": "İptal edildi", "completed": "Tamamlandı"}


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "status_labels": STATUS_LABELS}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Bu sayfayı görmek için giriş yapmalısınız.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.is_admin:
            flash("Bu alana erişim yetkiniz yok.", "danger")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


DEFAULT_PRICING = {"led_area": 1000, "light": 1000, "venue_0_50": 5000, "venue_51_100": 7500, "venue_101_150": 10000, "venue_151_plus": 15000}


def get_pricing():
    values = DEFAULT_PRICING.copy()
    for setting in PricingSetting.query.all():
        values[setting.setting_key] = Decimal(setting.amount)
    return values


def calculate_price(service, start_date, end_date, people_count, led_area=0, light_count=0):
    days = max((end_date - start_date).days + 1, 1)
    pricing = get_pricing()
    if people_count <= 50:
        venue_price = Decimal(pricing["venue_0_50"])
    elif people_count <= 100:
        venue_price = Decimal(pricing["venue_51_100"])
    elif people_count <= 150:
        venue_price = Decimal(pricing["venue_101_150"])
    else:
        venue_price = Decimal(pricing["venue_151_plus"])
    daily_total = Decimal(led_area) * Decimal(pricing["led_area"]) + venue_price + Decimal(light_count) * Decimal(pricing["light"])
    total = daily_total * days
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), days


def availability_error(start_date, end_date, service_id):
    blocked = BlockedDate.query.filter(BlockedDate.start_date <= end_date, BlockedDate.end_date >= start_date).first()
    if blocked:
        return "Seçtiğiniz tarihler kapalıdır."
    conflict = Reservation.query.filter(Reservation.service_id == service_id, Reservation.start_date <= end_date, Reservation.end_date >= start_date, Reservation.status.in_(["pending", "approved"])).first()
    return "Bu hizmet için seçtiğiniz tarihler dolu." if conflict else None


def make_reservation_no():
    return f"RES-{datetime.now():%Y%m%d}-{uuid4().hex[:5].upper()}"


@app.route("/")
def index():
    return render_template("index.html", services=Service.query.filter_by(is_active=True).limit(3).all())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = {key: request.form.get(key, "").strip() for key in ["first_name", "last_name", "username", "email", "phone"]}
        password = request.form.get("password", "")
        if not all(data.values()) or not password:
            flash("Lütfen tüm alanları doldurun.", "danger")
        elif password != request.form.get("password_confirm", ""):
            flash("Şifreler eşleşmiyor.", "danger")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", data["email"]):
            flash("Geçerli bir e-posta adresi girin.", "danger")
        elif User.query.filter((User.username == data["username"]) | (User.email == data["email"].lower())).first():
            flash("Bu kullanıcı adı veya e-posta zaten kullanılıyor.", "danger")
        else:
            data["email"] = data["email"].lower()
            user = User(**data)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Kayıt başarılı. Şimdi giriş yapabilirsiniz.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if user and user.is_active and user.check_password(request.form.get("password", "")):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("admin_dashboard" if user.is_admin else "dashboard"))
        flash("Kullanıcı adı veya şifre hatalı.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Güvenli şekilde çıkış yaptınız.", "success")
    return redirect(url_for("index"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        flash("E-posta adresiniz sistemde kayıtlıysa şifre sıfırlama talimatı hazırlanmıştır. SMTP bağlantısı eklenmeye hazırdır.", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.created_at.desc()).all()
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(5).all()
    return render_template("dashboard.html", reservations=reservations, notifications=notifications)


@app.route("/reservation/new", methods=["GET", "POST"])
@login_required
def reservation_new():
    services = Service.query.filter_by(is_active=True).all()
    if request.method == "POST":
        try:
            service = Service.query.filter_by(is_active=True).order_by(Service.id).first()
            start_date, end_date = parse_date(request.form["start_date"]), parse_date(request.form["end_date"])
            people = max(int(request.form.get("people_count", 1)), 1)
            if not service or start_date < date.today() or end_date < start_date:
                raise ValueError("Tarih veya hizmet bilgisi geçersiz.")
            error = availability_error(start_date, end_date, service.id)
            if error:
                raise ValueError(error)
            led_area = max(int(request.form.get("led_area", 0)), 0)
            light_count = max(int(request.form.get("light_count", 0)), 0)
            if led_area < 1:
                raise ValueError("LED ekran alanı en az 1 m² olmalıdır.")
            price, days = calculate_price(service, start_date, end_date, people, led_area, light_count)
            start_time = datetime.strptime(request.form["start_time"], "%H:%M").time()
            reservation = Reservation(reservation_no=make_reservation_no(), user_id=current_user().id, service_id=service.id, start_date=start_date, end_date=end_date, start_time=start_time, end_time=start_time, people_count=people, room_count=max(int(request.form.get("room_count", 0)), 0), vehicle_count=max(int(request.form.get("vehicle_count", 0)), 0), led_area=led_area, light_count=light_count, extra_services=request.form.get("extra_services", "").strip(), notes=request.form.get("notes", "").strip(), estimated_price=price)
            db.session.add(reservation)
            db.session.flush()
            db.session.add(Notification(user_id=current_user().id, message=f"{reservation.reservation_no} numaralı rezervasyon talebiniz oluşturuldu."))
            db.session.commit()
            flash("Rezervasyon talebiniz oluşturuldu.", "success")
            return redirect(url_for("reservation_detail", reservation_id=reservation.id))
        except (ValueError, KeyError):
            flash("Bilgileri kontrol edip tekrar deneyin.", "danger")
    return render_template("reservation_new.html", services=services, today=date.today().isoformat())


@app.route("/api/quote")
@login_required
def quote():
    try:
        service = Service.query.filter_by(is_active=True).order_by(Service.id).first()
        start_date, end_date = parse_date(request.args["start_date"]), parse_date(request.args["end_date"])
        people = max(int(request.args.get("people_count", 1)), 1)
        led_area = max(int(request.args.get("led_area", 0)), 0)
        light_count = max(int(request.args.get("light_count", 0)), 0)
        if not service or end_date < start_date:
            raise ValueError
        price, days = calculate_price(service, start_date, end_date, people, led_area, light_count)
        return jsonify({"price": str(price), "days": days, "available": availability_error(start_date, end_date, service.id) is None})
    except (ValueError, KeyError, TypeError):
        return jsonify({"error": "Geçerli rezervasyon bilgileri girin."}), 400


@app.route("/reservation/<int:reservation_id>")
@login_required
def reservation_detail(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if not reservation or (reservation.user_id != current_user().id and not current_user().is_admin):
        flash("Rezervasyon bulunamadı.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("reservation_detail.html", reservation=reservation)


@app.route("/reservation/<int:reservation_id>/cancel", methods=["POST"])
@login_required
def reservation_cancel(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation and reservation.user_id == current_user().id and reservation.status in ["pending", "approved"]:
        reservation.status = "cancelled"
        db.session.add(Notification(user_id=reservation.user_id, message=f"{reservation.reservation_no} numaralı rezervasyonunuz iptal edildi."))
        db.session.commit()
        flash("Rezervasyon iptal edildi.", "success")
    return redirect(url_for("reservation_detail", reservation_id=reservation_id))


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html", users=User.query.count(), reservations=Reservation.query.count(), pending=Reservation.query.filter_by(status="pending").count(), approved=Reservation.query.filter_by(status="approved").count(), rejected=Reservation.query.filter_by(status="rejected").count(), cancelled=Reservation.query.filter_by(status="cancelled").count(), total=sum((r.estimated_price for r in Reservation.query.all()), Decimal("0")))


@app.route("/admin/reservations")
@admin_required
def admin_reservations():
    query = Reservation.query
    if request.args.get("status"):
        query = query.filter_by(status=request.args["status"])
    reservations = query.order_by(Reservation.created_at.desc()).all()
    return render_template("admin/reservations.html", reservations=reservations)


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    if request.method == "POST":
        user = db.session.get(User, int(request.form.get("user_id", 0)))
        if user and user.id != current_user().id:
            user.is_active = request.form.get("is_active") == "1"
            db.session.commit()
            flash("Kullanıcı durumu güncellendi.", "success")
    return render_template("admin/users.html", users=User.query.order_by(User.created_at.desc()).all())


@app.route("/admin/reservation/<int:reservation_id>/status", methods=["POST"])
@admin_required
def admin_status(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    new_status = request.form.get("status")
    if reservation and new_status in STATUS_LABELS:
        reservation.status = new_status
        reservation.admin_note = request.form.get("admin_note", "").strip()
        db.session.add(Notification(user_id=reservation.user_id, message=f"{reservation.reservation_no} durumu: {STATUS_LABELS[new_status]}."))
        db.session.commit()
        flash("Rezervasyon durumu güncellendi.", "success")
    return redirect(url_for("admin_reservations"))


@app.route("/admin/services", methods=["GET", "POST"])
@admin_required
def admin_services():
    if request.method == "POST":
        try:
            for key in DEFAULT_PRICING:
                value = Decimal(request.form[key])
                if value < 0:
                    raise ValueError
                setting = PricingSetting.query.filter_by(setting_key=key).first()
                if not setting:
                    setting = PricingSetting(setting_key=key)
                    db.session.add(setting)
                setting.amount = value
            db.session.commit()
            flash("Fiyatlandırma ayarları güncellendi.", "success")
        except (ValueError, KeyError):
            flash("Fiyat değerlerini kontrol edin.", "danger")
    return render_template("admin/services.html", pricing=get_pricing())


@app.route("/admin/blocks", methods=["GET", "POST"])
@admin_required
def admin_blocks():
    if request.method == "POST":
        try:
            db.session.add(BlockedDate(start_date=parse_date(request.form["start_date"]), end_date=parse_date(request.form["end_date"]), reason=request.form.get("reason", "").strip()))
            db.session.commit()
            flash("Tarih aralığı kapatıldı.", "success")
        except (ValueError, KeyError):
            flash("Tarihleri kontrol edin.", "danger")
    return render_template("admin/blocks.html", blocks=BlockedDate.query.order_by(BlockedDate.start_date).all())


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", message="Aradığınız sayfa bulunamadı."), 404


@app.errorhandler(500)
def server_error(_error):
    db.session.rollback()
    return render_template("error.html", message="Bir hata oluştu. Lütfen tekrar deneyin."), 500


with app.app_context():
    db.create_all()
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    admin_email = os.environ.get("ADMIN_EMAIL")
    if admin_username and admin_password and admin_email:
        admin = User.query.filter((User.username == admin_username) | (User.email == admin_email.lower())).first()
        if not admin:
            admin = User(username=admin_username, email=admin_email.lower(), first_name="Site", last_name="Yöneticisi", phone="0000000000", is_admin=True, is_active=True)
            db.session.add(admin)
        admin.set_password(admin_password)
        admin.is_admin = True
        admin.is_active = True
    for pricing_key, pricing_amount in DEFAULT_PRICING.items():
        if not PricingSetting.query.filter_by(setting_key=pricing_key).first():
            db.session.add(PricingSetting(setting_key=pricing_key, amount=pricing_amount))
    reservation_columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(reservation)"))}
    if "led_area" not in reservation_columns:
        db.session.execute(text("ALTER TABLE reservation ADD COLUMN led_area INTEGER NOT NULL DEFAULT 0"))
    if "light_count" not in reservation_columns:
        db.session.execute(text("ALTER TABLE reservation ADD COLUMN light_count INTEGER NOT NULL DEFAULT 0"))
    db.session.commit()
    if not Service.query.first():
        db.session.add_all([Service(name="Standart Rezervasyon", description="Esnek tarih ve saat seçenekleriyle temel hizmet.", base_price=1000, per_person_price=250, per_day_price=500, unit="Günlük"), Service(name="Premium Paket", description="Daha kapsamlı ve öncelikli hizmet paketi.", base_price=2500, per_person_price=450, per_day_price=750, unit="Paket")])
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)
