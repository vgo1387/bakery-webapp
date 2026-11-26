from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)


class Bakery(db.Model):
    __tablename__ = 'bakeries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    phone = db.Column(db.String(20))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    bakery_type = db.Column(db.String(20), nullable=False, default='free')  # share/free
    status = db.Column(db.String(20), default='approved')  # pending/approved/rejected
    # حساب نانوایی (توسط مدیر ساخته می‌شود)
    username = db.Column(db.String(80), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    price_per_loaf = db.Column(db.Integer, nullable=False, default=0)
    price_per_bag = db.Column(db.Integer, nullable=False, default=0)
    working_hours_start = db.Column(db.String(5), default='06:00')
    working_hours_end = db.Column(db.String(5), default='18:00')
    working_days = db.Column(db.String(20), default='0,1,2,3,4,5')
    holidays = db.Column(db.String(200), default='')
    daily_capacity = db.Column(db.Integer, default=20)
    accepting_reservations = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reservations = db.relationship('Reservation', backref='bakery', lazy=True)

    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, pwd)

    def to_dict(self, with_capacity=True):
        d = {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'phone': self.phone,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'bakery_type': self.bakery_type,
            'status': self.status,
            'is_active': self.is_active,
            'price_per_loaf': self.price_per_loaf,
            'price_per_bag': self.price_per_bag,
            'working_hours_start': self.working_hours_start,
            'working_hours_end': self.working_hours_end,
            'working_days': self.working_days,
            'daily_capacity': self.daily_capacity,
            'accepting_reservations': self.accepting_reservations,
        }
        if with_capacity:
            d['today_capacity'] = get_today_capacity(self)
        return d



class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=True)   # نام و نام خانوادگی (از بات/فرم دریافت می‌شود)
    latitude = db.Column(db.Float, nullable=True)     # موقعیت مشتری (اجباری بعد از ورود)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None


class OTP(db.Model):
    __tablename__ = 'otps'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=True)      # شماره (برای پیامک و کاربران بات که شماره دادند)
    chat_id = db.Column(db.String(100), nullable=True)   # شناسه کاربر در بات (روبیکا/بله/ایتا)
    channel = db.Column(db.String(20), nullable=True)    # sms / bale / eitaa / rubika
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used = db.Column(db.Boolean, default=False)


class BotUser(db.Model):
    """نگاشت شناسه کاربر در بات به شماره موبایل و نام."""
    __tablename__ = 'bot_users'
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), unique=True, nullable=False)
    channel = db.Column(db.String(20), nullable=False)   # bale / eitaa / rubika
    phone = db.Column(db.String(20), nullable=True)
    name = db.Column(db.String(100), nullable=True)
    step = db.Column(db.String(20), default='none')   # none / waiting_name / done
    last_msg_id = db.Column(db.String(50), nullable=True)  # آخرین update_id پردازش‌شده (جلوگیری از تکرار)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BotSession(db.Model):
    """سشن ورود سریع — وقتی کاربر از بات وارد میشه، یک توکن تصادفی ساخته میشه.
    لینک: /api/bot/login?token=XXXX → لاگین خودکار + سشن عادی"""
    __tablename__ = 'bot_sessions'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    channel = db.Column(db.String(20), nullable=False)
    used = db.Column(db.Boolean, default=False)    # یک‌بار مصرف
    expires_at = db.Column(db.DateTime, nullable=False)


class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    delivery_code = db.Column(db.String(20), unique=True, nullable=False)
    bakery_id = db.Column(db.Integer, db.ForeignKey('bakeries.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_phone = db.Column(db.String(20), nullable=False)
    reservation_date = db.Column(db.Date, nullable=False)
    loaf_count = db.Column(db.Integer, nullable=False, default=1)
    bag_count = db.Column(db.Integer, nullable=False, default=0)
    bread_type = db.Column(db.String(50), default='بربری')
    status = db.Column(db.String(20), default='pending')  # pending/ready/waiting_confirm/delivered/cancelled
    total_price = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        from utils import jalali_str
        return {
            'id': self.id,
            'code': self.code,
            'delivery_code': self.delivery_code,
            'bakery_id': self.bakery_id,
            'user_phone': self.user_phone,
            'reservation_date': str(self.reservation_date),
            'reservation_date_jalali': jalali_str(self.reservation_date, True),
            'loaf_count': self.loaf_count,
            'bag_count': self.bag_count,
            'bread_type': self.bread_type,
            'status': self.status,
            'total_price': self.total_price,
        }


class DailyBakerySetting(db.Model):
    """ثبت تصمیم روزانه نانوا (ظرفیت/بستن/باز)"""
    __tablename__ = 'daily_bakery_settings'
    id = db.Column(db.Integer, primary_key=True)
    bakery_id = db.Column(db.Integer, db.ForeignKey('bakeries.id'), nullable=False)
    the_date = db.Column(db.Date, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=0)
    accepting = db.Column(db.Boolean, default=True)
    __table_args__ = (db.UniqueConstraint('bakery_id', 'the_date', name='uniq_setting_date'),)


# ---------- Helpers ----------
def get_capacity_for_date(bakery, target_date):
    """ظرفیت موثر یک روز: اگر نانوا برای آن روز تنظیم کرده از آن، وگرنه پیش‌فرض"""
    s = DailyBakerySetting.query.filter_by(bakery_id=bakery.id, the_date=target_date).first()
    if s:
        return s.capacity
    return bakery.daily_capacity


def get_today_capacity(bakery):
    """ظرفیت موثر امروز"""
    return get_capacity_for_date(bakery, date.today())


def get_today_accepting(bakery):
    today = date.today()
    s = DailyBakerySetting.query.filter_by(bakery_id=bakery.id, the_date=today).first()
    if s is not None:
        return s.accepting and bakery.accepting_reservations and bakery.is_active
    return bakery.accepting_reservations and bakery.is_active


def gen_code(length=6):
    import random, string
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


def parse_date(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return date.today()


def remaining_capacity(bakery, target_date):
    used = Reservation.query.filter(
        Reservation.bakery_id == bakery.id,
        Reservation.reservation_date == target_date,
        Reservation.status.in_(['pending', 'ready', 'waiting_confirm', 'delivered'])
    ).count()
    cap = get_capacity_for_date(bakery, target_date)
    return max(0, cap - used)


def is_bakery_open_on(bakery, target_date):
    if not bakery.is_active or bakery.status != 'approved':
        return False, 'inactive'
    if str(target_date) in [h.strip() for h in (bakery.holidays or '').split(',') if h.strip()]:
        return False, 'holiday'
    # تنظیم روزانه نانوا برای هر تاریخی (امروز یا آینده) اعمال می‌شود
    s = DailyBakerySetting.query.filter_by(bakery_id=bakery.id, the_date=target_date).first()
    if s is not None and s.accepting is False:
        return False, 'accepting_closed'
    if s is not None and s.capacity <= 0:
        return False, 'capacity_closed'
    py_weekday = target_date.weekday()
    our_weekday = (py_weekday + 2) % 7
    if str(our_weekday) not in (bakery.working_days or '').split(','):
        return False, 'closed_day'
    return True, 'ok'
