from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from models import db, Bakery, Reservation, DailyBakerySetting, get_today_capacity

bakery_bp = Blueprint('bakery', __name__)


@bakery_bp.route('/bakery/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        bakery = Bakery.query.filter_by(username=username).first()
        if bakery and bakery.check_password(password):
            session['bakery_id'] = bakery.id
            return redirect(url_for('bakery.dashboard'))
        return render_template('bakery_login.html', error='نام کاربری یا رمز عبور اشتباه است')
    return render_template('bakery_login.html')


@bakery_bp.route('/bakery/logout')
def logout():
    session.pop('bakery_id', None)
    return redirect(url_for('bakery.login'))


def current_bakery():
    bid = session.get('bakery_id')
    if bid:
        return Bakery.query.get(bid)
    return None


@bakery_bp.route('/bakery')
def dashboard():
    bakery = current_bakery()
    if not bakery:
        return redirect(url_for('bakery.login'))
    from utils import jalali_str
    today = date.today()
    reservations = Reservation.query.filter_by(bakery_id=bakery.id, reservation_date=today).order_by(Reservation.id).all()
    capacity = get_today_capacity(bakery)
    used = sum(1 for r in reservations if r.status in ('pending', 'ready', 'waiting_confirm', 'delivered'))
    remaining = max(0, capacity - used)
    setting = DailyBakerySetting.query.filter_by(bakery_id=bakery.id, the_date=today).first()
    accepting = setting.accepting if setting is not None else bakery.accepting_reservations

    # ۷ روز آینده برای مدیریت ظرفیت روزانه
    days = []
    for i in range(7):
        d = today + timedelta(days=i)
        s = DailyBakerySetting.query.filter_by(bakery_id=bakery.id, the_date=d).first()
        day_used = Reservation.query.filter(
            Reservation.bakery_id == bakery.id,
            Reservation.reservation_date == d,
            Reservation.status.in_(['pending', 'ready', 'waiting_confirm', 'delivered'])
        ).count()
        days.append({
            'date': d,
            'jalali': jalali_str(d, True),
            'capacity': s.capacity if s else bakery.daily_capacity,
            'accepting': s.accepting if s is not None else (bakery.accepting_reservations and bakery.is_active),
            'used': day_used,
            'is_today': i == 0,
        })

    return render_template(
        'bakery_dashboard.html', bakery=bakery, reservations=reservations,
        capacity=capacity, remaining=remaining, used=used, accepting=accepting,
        today=today, today_jalali=jalali_str(today, True), days=days
    )


# ---------- API نانوایی ----------
@bakery_bp.route('/api/bakery/myself')
def api_myself():
    bakery = current_bakery()
    if not bakery:
        return jsonify({'success': False, 'error': 'ورود نامعتبر'}), 401
    return jsonify({'success': True, 'bakery': bakery.to_dict()})


@bakery_bp.route('/api/bakery/today')
def api_today():
    bakery = current_bakery()
    if not bakery:
        return jsonify({'success': False, 'error': 'ورود نامعتبر'}), 401
    today = date.today()
    reservations = Reservation.query.filter_by(bakery_id=bakery.id, reservation_date=today).order_by(Reservation.id).all()
    capacity = get_today_capacity(bakery)
    setting = DailyBakerySetting.query.filter_by(bakery_id=bakery.id, the_date=today).first()
    accepting = setting.accepting if setting is not None else bakery.accepting_reservations
    return jsonify({
        'success': True,
        'capacity': capacity,
        'accepting': accepting,
        'reservations': [r.to_dict() for r in reservations],
    })


@bakery_bp.route('/api/bakery/settings', methods=['POST'])
def api_settings():
    bakery = current_bakery()
    if not bakery:
        return jsonify({'success': False, 'error': 'ورود نامعتبر'}), 401
    data = request.get_json(silent=True) or {}
    target = date.today()
    if data.get('date'):
        try:
            target = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'error': 'تاریخ نامعتبر است'}), 400
    setting = DailyBakerySetting.query.filter_by(bakery_id=bakery.id, the_date=target).first()
    if not setting:
        setting = DailyBakerySetting(bakery_id=bakery.id, the_date=target)
        db.session.add(setting)

    if 'capacity' in data:
        try:
            cap = int(data['capacity'])
            if cap < 0 or cap > 1000:
                return jsonify({'success': False, 'error': 'ظرفیت نامعتبر است'}), 400
            setting.capacity = cap
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'ظرفیت نامعتبر است'}), 400

    if 'accepting' in data:
        setting.accepting = bool(data['accepting'])

    db.session.commit()
    return jsonify({'success': True})


@bakery_bp.route('/api/bakery/reservation/<code>/status', methods=['POST'])
def api_set_status(code):
    bakery = current_bakery()
    if not bakery:
        return jsonify({'success': False, 'error': 'ورود نامعتبر'}), 401
    r = Reservation.query.filter_by(code=code, bakery_id=bakery.id).first()
    if not r:
        return jsonify({'success': False, 'error': 'نوبت یافت نشد'}), 404
    data = request.get_json(silent=True) or {}
    status = data.get('status')
    allowed = ('pending', 'ready', 'waiting_confirm', 'delivered', 'cancelled')
    if status not in allowed:
        return jsonify({'success': False, 'error': 'وضعیت نامعتبر'}), 400
    r.status = status
    db.session.commit()
    return jsonify({'success': True, 'status': r.status})


@bakery_bp.route('/api/bakery/verify-code', methods=['POST'])
def api_verify_code():
    """بررسی کد تحویل مشتری هنگام تحویل گرفتن نان"""
    bakery = current_bakery()
    if not bakery:
        return jsonify({'success': False, 'error': 'ورود نامعتبر'}), 401
    data = request.get_json(silent=True) or {}
    delivery_code = str(data.get('delivery_code') or '').strip()
    r = Reservation.query.filter_by(delivery_code=delivery_code, bakery_id=bakery.id, reservation_date=date.today()).first()
    if not r:
        return jsonify({'success': False, 'error': 'کد تحویل یافت نشد'}), 404
    return jsonify({'success': True, 'reservation': r.to_dict()})
