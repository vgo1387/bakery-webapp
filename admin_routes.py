from datetime import date, datetime
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from models import db, Bakery, User, Reservation
from seed import ADMIN_USERNAME, ADMIN_PASSWORD

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin.dashboard'))
        return render_template('admin_login.html', error='نام کاربری یا رمز عبور اشتباه است')
    return render_template('admin_login.html')


@admin_bp.route('/admin/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin.login'))


def is_admin():
    return session.get('admin') is True


@admin_bp.route('/admin')
def dashboard():
    if not is_admin():
        return redirect(url_for('admin.login'))
    total_bakeries = Bakery.query.count()
    active_bakeries = Bakery.query.filter_by(is_active=True).count()
    total_users = User.query.count()
    total_reservations = Reservation.query.count()
    today = date.today()
    today_reservations = Reservation.query.filter_by(reservation_date=today).count()
    bakeries = Bakery.query.order_by(Bakery.id.desc()).all()
    reservations = Reservation.query.order_by(Reservation.created_at.desc()).limit(20).all()
    return render_template(
        'admin_dashboard.html',
        total_bakeries=total_bakeries, active_bakeries=active_bakeries,
        total_users=total_users, total_reservations=total_reservations,
        today_reservations=today_reservations, bakeries=bakeries, reservations=reservations,
    )


@admin_bp.route('/admin/bakeries')
def bakeries_list():
    if not is_admin():
        return redirect(url_for('admin.login'))
    bakeries = Bakery.query.order_by(Bakery.id.desc()).all()
    return render_template('admin_bakeries.html', bakeries=bakeries)


# ---------- مدیریت مشتری‌ها ----------
@admin_bp.route('/admin/customers')
def customers_list():
    if not is_admin():
        return redirect(url_for('admin.login'))
    import json
    users = User.query.order_by(User.id.desc()).all()
    customers_json = []
    for u in users:
        reservations = Reservation.query.filter_by(user_phone=u.phone).order_by(
            Reservation.created_at.desc()).all()
        customers_json.append({
            'id': u.id,
            'phone': u.phone,
            'name': u.name,
            'location': (f"{u.latitude:.4f}, {u.longitude:.4f}"
                         if u.latitude is not None and u.longitude is not None else 'ثبت نشده'),
            'reservations': [
                {
                    'code': r.code,
                    'bakery': r.bakery.name if r.bakery else '—',
                    'date': str(r.reservation_date),
                    'status': r.status,
                } for r in reservations
            ],
        })
    return render_template(
        'admin_customers.html',
        users=users,
        customers_json=json.dumps(customers_json, ensure_ascii=False),
    )


@admin_bp.route('/admin/customers/<int:user_id>/delete', methods=['POST'])
def customer_delete(user_id):
    if not is_admin():
        return redirect(url_for('admin.login'))
    user = User.query.get_or_404(user_id)
    Reservation.query.filter_by(user_phone=user.phone).delete()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin.customers_list'))


@admin_bp.route('/admin/bakeries/new', methods=['GET', 'POST'])
def bakery_new():
    if not is_admin():
        return redirect(url_for('admin.login'))
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        address = (request.form.get('address') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        bakery_type = request.form.get('bakery_type') or 'free'
        price_per_loaf = int(request.form.get('price_per_loaf') or 0)
        price_per_bag = int(request.form.get('price_per_bag') or 0)
        working_hours_start = request.form.get('working_hours_start') or '06:00'
        working_hours_end = request.form.get('working_hours_end') or '18:00'
        working_days = request.form.get('working_days') or '0,1,2,3,4,5'
        daily_capacity = int(request.form.get('daily_capacity') or 20)
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        latitude = float(request.form.get('latitude') or 35.7448)
        longitude = float(request.form.get('longitude') or 51.3753)

        if not name or not address or not username or not password:
            return render_template('admin_bakery_form.html', error='فیلدهای ضروری را پر کنید')

        if Bakery.query.filter_by(username=username).first():
            return render_template('admin_bakery_form.html', error='این نام کاربری قبلاً استفاده شده است')

        bakery = Bakery(
            name=name, address=address, phone=phone,
            latitude=latitude, longitude=longitude,
            bakery_type=bakery_type, status='approved',
            price_per_loaf=price_per_loaf, price_per_bag=price_per_bag,
            working_hours_start=working_hours_start, working_hours_end=working_hours_end,
            working_days=working_days, daily_capacity=daily_capacity,
            username=username, accepting_reservations=True, is_active=True,
        )
        bakery.set_password(password)
        db.session.add(bakery)
        db.session.commit()
        return redirect(url_for('admin.bakeries_list'))

    return render_template('admin_bakery_form.html')


@admin_bp.route('/admin/bakeries/<int:bakery_id>/edit', methods=['GET', 'POST'])
def bakery_edit(bakery_id):
    if not is_admin():
        return redirect(url_for('admin.login'))
    bakery = Bakery.query.get_or_404(bakery_id)
    if request.method == 'POST':
        bakery.name = (request.form.get('name') or bakery.name).strip()
        bakery.address = (request.form.get('address') or bakery.address).strip()
        bakery.phone = (request.form.get('phone') or bakery.phone).strip()
        bakery.bakery_type = request.form.get('bakery_type') or bakery.bakery_type
        bakery.price_per_loaf = int(request.form.get('price_per_loaf') or bakery.price_per_loaf)
        bakery.price_per_bag = int(request.form.get('price_per_bag') or bakery.price_per_bag)
        bakery.working_hours_start = request.form.get('working_hours_start') or bakery.working_hours_start
        bakery.working_hours_end = request.form.get('working_hours_end') or bakery.working_hours_end
        bakery.working_days = request.form.get('working_days') or bakery.working_days
        bakery.daily_capacity = int(request.form.get('daily_capacity') or bakery.daily_capacity)
        try:
            bakery.latitude = float(request.form.get('latitude') or bakery.latitude)
            bakery.longitude = float(request.form.get('longitude') or bakery.longitude)
        except (TypeError, ValueError):
            pass
        password = request.form.get('password') or ''
        if password:
            bakery.set_password(password)
        db.session.commit()
        return redirect(url_for('admin.bakeries_list'))
    return render_template('admin_bakery_form.html', bakery=bakery)


@admin_bp.route('/admin/bakeries/<int:bakery_id>/toggle', methods=['POST'])
def bakery_toggle(bakery_id):
    if not is_admin():
        return jsonify({'success': False, 'error': 'دسترسی غیرمجاز'}), 401
    bakery = Bakery.query.get_or_404(bakery_id)
    bakery.is_active = not bakery.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': bakery.is_active})


@admin_bp.route('/admin/bakeries/<int:bakery_id>/delete', methods=['POST'])
def bakery_delete(bakery_id):
    if not is_admin():
        return redirect(url_for('admin.login'))
    bakery = Bakery.query.get_or_404(bakery_id)
    db.session.delete(bakery)
    db.session.commit()
    return redirect(url_for('admin.bakeries_list'))

