import random
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from models import db, Bakery, User, OTP, Reservation, remaining_capacity, is_bakery_open_on, gen_code, parse_date
import sms

customer_bp = Blueprint('customer', __name__)


@customer_bp.route('/')
def index():
    user = current_user()
    # مکان اجباری: اگه لاگینه ولی مکان ثبت نکرده → صفحه مکان
    if user and not user.has_location:
        return redirect(url_for('customer.location_page'))
    return render_template('index.html', user=user)


def current_user():
    uid = session.get('user_id')
    if uid:
        return User.query.get(uid)
    return None


# ---------- OTP login ----------
@customer_bp.route('/login')
def login_page():
    return render_template('otp_login.html')


@customer_bp.route('/api/otp/request', methods=['POST'])
def otp_request():
    """ورود ساده با شماره موبایل (کد پیامکی به‌زودی فعال می‌شود)"""
    data = request.get_json(silent=True) or {}
    phone = str(data.get('phone') or '').strip()
    if not (len(phone) == 11 and phone.startswith('09') and phone.isdigit()):
        return jsonify({'success': False, 'error': 'شماره موبایل معتبر وارد کنید'}), 400

    # ثبت‌نام خودکار در صورت نبود کاربر + ورود مستقیم
    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(phone=phone)
        db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    return jsonify({'success': True, 'need_location': not user.has_location})


@customer_bp.route('/api/bot/login', methods=['GET'])
def bot_login():
    """لینک ورود سریع از بات — /api/bot/login?token=XXXX
    توکن یک‌بار مصرف ۵ دقیقه‌ای که بات می‌فرسته."""
    from models import BotSession
    token = request.args.get('token', '').strip()
    if not token:
        return redirect(url_for('customer.login_page'))

    bot_session = BotSession.query.filter_by(token=token, used=False).first()
    if not bot_session:
        return render_template('otp_login.html', bot_error='این لینک منقضی شده یا قبلاً استفاده شده. لطفاً از بات دوباره کد بگیرید.')

    if datetime.utcnow() > bot_session.expires_at:
        return render_template('otp_login.html', bot_error='این لینک منقضی شده. لطفاً از بات دوباره کد بگیرید.')

    bot_session.used = True
    user = User.query.filter_by(phone=bot_session.phone).first()
    if not user:
        user = User(phone=bot_session.phone, name=bot_session.name)
        db.session.add(user)
    else:
        if bot_session.name:
            user.name = bot_session.name

    db.session.commit()
    session['user_id'] = user.id
    # مکان اجباری بعد از ورود اولیه
    if not user.has_location:
        return redirect(url_for('customer.location_page'))
    return redirect(url_for('customer.index'))


@customer_bp.route('/api/otp/verify', methods=['POST'])
def otp_verify():
    data = request.get_json(silent=True) or {}
    phone = str(data.get('phone') or '').strip()
    code = str(data.get('code') or '').strip()

    # اول با شماره و کد (حالت پیامک) — اگه کد فقط داده شده (بات)، با کد alone هم جستجو کن
    if phone:
        otp = OTP.query.filter_by(phone=phone, code=code, used=False).order_by(OTP.id.desc()).first()
    else:
        otp = OTP.query.filter_by(code=code, used=False).order_by(OTP.id.desc()).first()

    if not otp:
        return jsonify({'success': False, 'error': 'کد نامعتبر است'}), 400
    if datetime.utcnow() - otp.created_at > timedelta(minutes=5):
        return jsonify({'success': False, 'error': 'کد منقضی شده است'}), 400

    otp.used = True
    user_phone = phone or (otp.phone or '')

    if not user_phone:
        return jsonify({'success': False, 'error': 'کد نامعتبر است'}), 400

    user = User.query.filter_by(phone=user_phone).first()
    if not user:
        user = User(phone=user_phone)
        db.session.add(user)
    db.session.commit()

    session['user_id'] = user.id
    # مکان اجباری بعد از ورود (فرانت با success + need_location هندل می‌کند)
    return jsonify({'success': True, 'need_location': not user.has_location})


@customer_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('customer.index'))


# ---------- موقعیت اجباری مشتری ----------
@customer_bp.route('/customer/location', methods=['GET', 'POST'])
def location_page():
    user = current_user()
    if not user:
        return redirect(url_for('customer.login_page'))
    has_location = user.latitude is not None and user.longitude is not None
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        try:
            lat = float(data.get('latitude'))
            lng = float(data.get('longitude'))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'مختصات نامعتبر'}), 400
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return jsonify({'success': False, 'error': 'مختصات خارج از محدوده'}), 400
        user.latitude = lat
        user.longitude = lng
        db.session.commit()
        return jsonify({'success': True})
    return render_template('customer_location.html', user=user, has_location=has_location)


# ---------- تنظیمات مشتری ----------
@customer_bp.route('/customer/settings', methods=['GET', 'POST'])
def settings_page():
    user = current_user()
    if not user:
        return redirect(url_for('customer.login_page'))
    saved = False
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if name:
            user.name = name[:100]
        db.session.commit()
        saved = True
    return render_template('customer_settings.html', user=user, saved=saved)


@customer_bp.route('/customer/settings/edit')
def profile_edit_page():
    user = current_user()
    if not user:
        return redirect(url_for('customer.login_page'))
    return render_template('customer_profile_edit.html', user=user)


# ---------- API: ذخیره مکان (از صفحه مکان) ----------
@customer_bp.route('/api/customer/location/save', methods=['POST'])
def api_save_location():
    user = current_user()
    if not user:
        return jsonify({'success': False, 'error': 'ابتدا وارد شوید'}), 401
    data = request.get_json(silent=True) or {}
    try:
        lat = float(data.get('latitude'))
        lng = float(data.get('longitude'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'مختصات نامعتبر'}), 400
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({'success': False, 'error': 'مختصات خارج از محدوده'}), 400
    user.latitude = lat
    user.longitude = lng
    db.session.commit()
    return jsonify({'success': True})


# ---------- API: ذخیره پروفایل ----------
@customer_bp.route('/api/customer/profile/save', methods=['POST'])
def api_save_profile():
    user = current_user()
    if not user:
        return jsonify({'success': False, 'error': 'ابتدا وارد شوید'}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'نام را وارد کنید'}), 400
    user.name = name[:100]
    db.session.commit()
    return jsonify({'success': True})


@customer_bp.route('/bakeries/<int:bakery_id>')
def bakery_detail(bakery_id):
    bakery = Bakery.query.get_or_404(bakery_id)
    return render_template('bakery_detail.html', bakery=bakery)


@customer_bp.route('/bakeries/<int:bakery_id>/reserve')
def reserve_page(bakery_id):
    bakery = Bakery.query.get_or_404(bakery_id)
    user = current_user()
    if not user:
        return redirect(url_for('customer.login_page'))
    return render_template('reserve.html', bakery=bakery)


@customer_bp.route('/reservations/<code>')
def confirmation_page(code):
    reservation = Reservation.query.filter_by(code=code).first_or_404()
    from utils import qr_svg_base64
    qr_data = qr_svg_base64(reservation.delivery_code)
    return render_template('confirmation.html', r=reservation, bakery=reservation.bakery,
                           qr_data=qr_data, user=current_user())


# ---------- Bakeries & reservations ----------
@customer_bp.route('/api/bakeries')
def api_bakeries():
    bakeries = Bakery.query.filter_by(is_active=True, status='approved').all()
    return jsonify([b.to_dict() for b in bakeries])


@customer_bp.route('/api/bakeries/<int:bakery_id>')
def api_bakery_detail(bakery_id):
    bakery = Bakery.query.get_or_404(bakery_id)
    return jsonify(bakery.to_dict())


@customer_bp.route('/api/bakeries/<int:bakery_id>/capacity')
def api_capacity(bakery_id):
    bakery = Bakery.query.get_or_404(bakery_id)
    target = parse_date(request.args.get('date'))
    open_now, reason = is_bakery_open_on(bakery, target)
    if not open_now:
        return jsonify({'available': False, 'remaining': 0, 'total': bakery.daily_capacity, 'reason': reason})
    remaining = remaining_capacity(bakery, target)
    return jsonify({
        'available': remaining > 0,
        'remaining': remaining,
        'total': bakery.daily_capacity,
        'reason': 'ok' if remaining > 0 else 'capacity_full',
        'date': str(target),
    })


@customer_bp.route('/api/reservations', methods=['POST'])
def api_create_reservation():
    user = current_user()
    if not user:
        return jsonify({'success': False, 'error': 'ابتدا وارد شوید'}), 401

    data = request.get_json(silent=True) or {}
    bakery_id = data.get('bakeryId')
    loaf_count = int(data.get('loafCount') or 0)
    bag_count = int(data.get('bagCount') or 0)
    bread_type = data.get('breadType') or 'بربری'
    target = parse_date(data.get('date'))

    if loaf_count < 1 or loaf_count > 20 or bag_count < 0 or bag_count > 20:
        return jsonify({'success': False, 'error': 'تعداد نامعتبر است'}), 400

    bakery = Bakery.query.get(bakery_id)
    if not bakery:
        return jsonify({'success': False, 'error': 'نانوایی یافت نشد'}), 404

    dup = Reservation.query.filter_by(
        user_phone=user.phone, reservation_date=target, status='pending'
    ).first()
    if dup:
        return jsonify({'success': False, 'error': 'شما برای این تاریخ یک نوبت فعال دارید'}), 409

    open_now, reason = is_bakery_open_on(bakery, target)
    if not open_now:
        return jsonify({'success': False, 'error': 'نانوایی در این تاریخ نوبت نمی‌پذیرد'}), 400

    if remaining_capacity(bakery, target) < 1:
        return jsonify({'success': False, 'error': 'ظرفیت این روز تکمیل شده است'}), 409

    reservation = Reservation(
        code=gen_code(),
        delivery_code=gen_code(4),
        bakery_id=bakery.id,
        user_id=user.id,
        user_phone=user.phone,
        reservation_date=target,
        loaf_count=loaf_count,
        bag_count=bag_count,
        bread_type=bread_type,
        status='pending',
        total_price=loaf_count * bakery.price_per_loaf + bag_count * bakery.price_per_bag,
    )
    db.session.add(reservation)
    db.session.commit()
    return jsonify({'success': True, 'reservation': reservation.to_dict()}), 201


@customer_bp.route('/api/reservations/<code>', methods=['GET'])
def api_reservation(code):
    r = Reservation.query.filter_by(code=code).first()
    if not r:
        return jsonify({'success': False, 'error': 'یافت نشد'}), 404
    return jsonify({'success': True, 'reservation': r.to_dict()})


@customer_bp.route('/api/my-reservations')
def api_my_reservations():
    user = current_user()
    if not user:
        return jsonify({'success': False, 'error': 'ابتدا وارد شوید'}), 401
    from utils import qr_svg_base64
    rows = Reservation.query.filter_by(user_phone=user.phone).order_by(Reservation.reservation_date.desc()).all()
    result = []
    for r in rows:
        d = r.to_dict()
        d['bakery_name'] = r.bakery.name if r.bakery else ''
        if r.bakery:
            d['bakery_lat'] = r.bakery.latitude
            d['bakery_lng'] = r.bakery.longitude
        if r.status not in ('cancelled', 'delivered'):
            d['qr_data'] = qr_svg_base64(r.delivery_code)
        result.append(d)
    return jsonify({'success': True, 'reservations': result})


@customer_bp.route('/api/notifications/count')
def api_notifications_count():
    """تعداد نوبت‌های آماده دریافت (برای زنگوله اعلان)"""
    user = current_user()
    if not user:
        return jsonify({'success': True, 'count': 0})
    count = Reservation.query.filter_by(user_phone=user.phone, status='ready').count()
    return jsonify({'success': True, 'count': count})


@customer_bp.route('/my-reservations')
def my_reservations_page():
    user = current_user()
    if user and not user.has_location:
        return redirect(url_for('customer.location_page'))
    return render_template('my_reservations.html', user=user)


@customer_bp.route('/api/reservations/<code>/cancel', methods=['POST'])
def api_cancel_reservation(code):
    r = Reservation.query.filter_by(code=code).first()
    if not r:
        return jsonify({'success': False, 'error': 'یافت نشد'}), 404
    if r.status in ('delivered', 'cancelled'):
        return jsonify({'success': False, 'error': 'این نوبت قابل لغو نیست'}), 400
    r.status = 'cancelled'
    db.session.commit()
    return jsonify({'success': True})

