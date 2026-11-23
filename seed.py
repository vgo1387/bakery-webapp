from datetime import date
from models import db, Bakery, User
from werkzeug.security import generate_password_hash

# حساب مدیر سامانه (برای ورود به پنل مدیریت)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'


def seed_data():
    # اگر هیچ نانوایی‌ای نباشد، چند نمونه آزمایشی می‌سازیم
    if Bakery.query.count() == 0:
        samples = [
            ('نانوایی سنتی بربری رضایی', 'تهران، خیابان آزادی، نبش کوچه بهار', '02166554433',
             35.7005, 51.3905, 'share', 15000, 5000, '07:00', '20:00', 'rezaei'),
            ('نانوایی سنگک پورمند', 'تهران، خیابان ولیعصر، بالاتر از پارک ساعی', '02188776655',
             35.7560, 51.4100, 'free', 20000, 6000, '06:30', '19:00', 'pourmand'),
        ]
        for name, addr, phone, lat, lng, btype, pl, pb, hs, he, uname in samples:
            b = Bakery(
                name=name, address=addr, phone=phone, latitude=lat, longitude=lng,
                bakery_type=btype, status='approved',
                price_per_loaf=pl, price_per_bag=pb,
                working_hours_start=hs, working_hours_end=he,
                working_days='0,1,2,3,4,5', daily_capacity=20,
                username=uname, accepting_reservations=True,
            )
            b.set_password('test123')
            db.session.add(b)
        db.session.commit()
