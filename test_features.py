"""تست قابلیت‌های جدید: تقویم شمسی، QR، اعلان، ظرفیت روزهای آینده"""
import re
from app import app
from models import db, Bakery, Reservation


def get_last_otp(phone):
    """استخراج آخرین کد OTP از فایل لاگ پیامک (کد در انتهای خط است)"""
    with open('sms_log.txt', encoding='utf-8') as f:
        lines = [l for l in f.read().strip().split('\n') if phone in l]
    return re.search(r'(\d{4})\s*$', lines[-1]).group(1)


def fresh_login(client, phone):
    """ورود مستقیم با شماره (کد پیامکی فعلاً غیرفعال است)"""
    r = client.post('/api/otp/request', json={'phone': phone, 'channel': 'sms'})
    return r


def main():
    with app.app_context():
        db.create_all()
        from seed import seed_data
        seed_data()
        client = app.test_client()
        ok = []

        # 1) صفحه اصلی
        r = client.get('/')
        ok.append(('GET /', r.status_code == 200))

        # 2) ورود مشتری با شماره (بدون کد — کد پیامکی بعداً فعال می‌شود)
        r = fresh_login(client, '09120000001')
        ok.append(('login by phone', r.status_code == 200 and r.get_json()['success']))

        # 3) گرفتن نوبت برای اولین روز کاری آینده (جمعه‌ها بسته است)
        from datetime import date, timedelta
        target = None
        for off in range(1, 8):
            d = date.today() + timedelta(days=off)
            if (d.weekday() + 2) % 7 != 6:  # 6 = جمعه در تقویم ایرانی
                target = d.isoformat()
                break
        r = client.post('/api/reservations', json={
            'bakeryId': 1, 'date': target, 'loafCount': 2, 'bagCount': 1, 'breadType': 'بربری'})
        ok.append(('create reservation', r.status_code == 201))
        if r.status_code != 201:
            print('debug:', r.get_json())
            raise SystemExit('reservation failed')
        res = r.get_json()['reservation']
        jtext = res['reservation_date_jalali']
        ok.append(('jalali in to_dict', ('آبان' in jtext) or ('آذر' in jtext) or ('دی' in jtext)))

        # 4) صفحه تأیید: تاریخ شمسی + QR
        r = client.get(f"/reservations/{res['code']}")
        html = r.get_data(as_text=True)
        ok.append(('confirmation 200', r.status_code == 200))
        ok.append(('confirmation has QR', 'data:image/svg+xml;base64' in html))
        ok.append(('confirmation jalali', '۱۴۰' in html))

        # 5) زنگوله اعلان: باید صفر باشد
        r = client.get('/api/notifications/count')
        ok.append(('notifications count 0', r.get_json()['count'] == 0))

        # 6) لاگین نانوا و اعلام آماده شدن
        r = client.post('/bakery/login', data={'username': 'rezaei', 'password': 'test123'})
        ok.append(('bakery login', r.status_code == 302))
        r = client.post(f"/api/bakery/reservation/{res['code']}/status", json={'status': 'ready'})
        ok.append(('set ready', r.status_code == 200))

        # 7) حالا اعلان باید ۱ باشد
        r = client.get('/api/notifications/count')
        ok.append(('notifications count 1', r.get_json()['count'] == 1))

        # 8) my-reservations شامل qr_data و تاریخ شمسی
        r = client.get('/api/my-reservations')
        rows = r.get_json()['reservations']
        mine = [x for x in rows if x['code'] == res['code']][0]
        ok.append(('my-res has qr', 'qr_data' in mine and mine['qr_data'].startswith('data:image/svg')))
        ok.append(('my-res jalali', '۱۴۰' in mine['reservation_date_jalali']))

        # 9) ظرفیت روزهای آینده: تنظیم برای روز دیگر
        d2 = (date.today() + timedelta(days=3)).isoformat()
        r = client.post('/api/bakery/settings', json={'date': d2, 'capacity': 9, 'accepting': False})
        ok.append(('day settings save', r.status_code == 200))
        from models import DailyBakerySetting
        s = DailyBakerySetting.query.filter_by(bakery_id=1, the_date=date.today() + timedelta(days=3)).first()
        ok.append(('day settings persisted', s is not None and s.capacity == 9 and s.accepting is False))

        # 10) رزرو برای روز بسته باید رد شود
        client2 = app.test_client()
        r2 = fresh_login(client2, '09120000002')
        if not (r2.status_code == 200 and r2.get_json()['success']):
            print('debug login2:', r2.get_json())
            raise SystemExit('login2 failed')
        r = client2.post('/api/reservations', json={
            'bakeryId': 1, 'date': d2, 'loafCount': 1, 'bagCount': 0, 'breadType': 'بربری'})
        ok.append(('closed day rejected', r.status_code == 400))

        # 11) رندر داشبورد نانوا با روزها
        r = client.get('/bakery')
        html = r.get_data(as_text=True)
        ok.append(('bakery dashboard 200', r.status_code == 200))
        ok.append(('days manager rendered', ('days-manager' in html) and ('day-row' in html)))

        # پاکسازی داده تست
        for phone in ('09120000001', '09120000002'):
            for x in Reservation.query.filter_by(user_phone=phone).all():
                db.session.delete(x)
        # تنظیمات روزانه‌ای که در تست ساختیم هم پاک شود تا اجرای بعدی خراب نشود
        DailyBakerySetting.query.filter_by(bakery_id=1, the_date=date.today() + timedelta(days=3)).delete()
        db.session.commit()

        print('\n===== TEST RESULTS =====')
        all_pass = True
        for name, passed in ok:
            print(('PASS' if passed else 'FAIL'), '-', name)
            all_pass = all_pass and passed
        print('========================')
        print('ALL PASSED' if all_pass else 'SOME FAILED')


if __name__ == '__main__':
    main()
