import os
import socket
from datetime import date, datetime
import random
import string
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from models import db


def get_local_ips():
    """یافتن IPهای محلی لپ‌تاپ برای دسترسی گوشی‌ها از طریق هات‌اسپات/شبکه"""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.'):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def create_app():
    app = Flask(__name__)
    db_path = os.environ.get('DATABASE_PATH') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bakery.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # در استقرار (Render) حتماً متغیر محیطی SECRET_KEY تنظیم شود
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key')
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', '0') == '1'
    db.init_app(app)

    # cache-busting خودکار برای فایل‌های static: هر تغییر فایل → لینک جدید → مرورگر نسخه تازه می‌گیرد
    @app.template_global()
    def static_v(filename):
        filepath = os.path.join(app.static_folder, filename.replace('/', os.sep))
        try:
            v = int(os.stat(filepath).st_mtime)
        except OSError:
            v = 0
        return f'/static/{filename}?v={v}'

    with app.app_context():
        # مقداردهی اولیه دیتابیس (idempotent) — برای اجرا با gunicorn لازم است
        db.create_all()
        # مایگریشن سبک: اضافه‌کردن ستون‌های جدید به جدول‌های موجود
        from sqlalchemy import text as _text, inspect as _inspect
        insp = _inspect(db.engine)
        cols = [c['name'] for c in insp.get_columns('otps')]
        if 'chat_id' not in cols:
            db.session.execute(_text('ALTER TABLE otps ADD COLUMN chat_id VARCHAR(100)'))
        if 'channel' not in cols:
            db.session.execute(_text('ALTER TABLE otps ADD COLUMN channel VARCHAR(20)'))
        ucols = [c['name'] for c in insp.get_columns('users')]
        if 'name' not in ucols:
            db.session.execute(_text('ALTER TABLE users ADD COLUMN name VARCHAR(100)'))
        if 'latitude' not in ucols:
            db.session.execute(_text('ALTER TABLE users ADD COLUMN latitude FLOAT'))
        if 'longitude' not in ucols:
            db.session.execute(_text('ALTER TABLE users ADD COLUMN longitude FLOAT'))
        db.session.commit()
        from seed import seed_data
        seed_data()
        # بات‌ها: فعلاً خاموش — برای فعال‌سازی متغیر محیطی BOTS_ENABLED=1 را ست کنید
        try:
            import os as _os
            if _os.environ.get('BOTS_ENABLED', '') == '1':
                import sms
                started = sms.start_bot_polling(app)
                if started:
                    print(f'  [OK] Bot polling started for: {", ".join(started)}')
                else:
                    print('  [WARN] No bot token configured — polling skipped')
            else:
                print('  [INFO] Bots are OFFLINE (set BOTS_ENABLED=1 to enable)')
        except Exception as e:
            import traceback
            print(f'  [ERROR] Bot polling FAILED: {e}')
            traceback.print_exc()

    from customer_routes import customer_bp
    from bakery_routes import bakery_bp
    from admin_routes import admin_bp
    app.register_blueprint(customer_bp)
    app.register_blueprint(bakery_bp)
    app.register_blueprint(admin_bp)

    from utils import jalali_str
    app.jinja_env.filters['jalali'] = jalali_str

    @app.context_processor
    def inject_user():
        from models import User
        uid = session.get('user_id')
        user = User.query.get(uid) if uid else None
        # آدرس کاشی نقشه — قابل تنظیم با متغیر محیطی TILE_URL (مثلاً کاشی ایرانی نشان با کلید API)
        tile_url = os.environ.get('TILE_URL') or 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
        return {'user': user, 'tile_url': tile_url}

    @app.route('/manifest.json')
    def manifest():
        from flask import send_from_directory
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

    @app.route('/sw.js')
    def service_worker():
        from flask import send_from_directory
        return send_from_directory('static', 'sw.js', mimetype='application/javascript')

    @app.route('/connect-qr')
    def connect_qr():
        """صفحه QR برای اتصال مشتری‌ها از طریق هات‌اسپات/شبکه محلی"""
        from utils import qr_svg_base64
        ips = [ip for ip in get_local_ips() if not ip.startswith('169.254.')]
        # اولویت با آی‌پی هات‌اسپات ویندوز (پیش‌فرض 192.168.137.1)
        best = next((ip for ip in ips if ip.startswith('192.168.137.')), None)
        if not best and ips:
            best = ips[0]
        url = f'http://{best}:5000/' if best else 'http://127.0.0.1:5000/'
        return render_template('connect_qr.html', qr=qr_svg_base64(url), url=url, ips=ips)

    @app.route('/robots.txt')
    def robots_txt():
        from flask import send_from_directory
        return send_from_directory('static', 'robots.txt', mimetype='text/plain')

    @app.route('/sitemap.xml')
    def sitemap_xml():
        """نقشه سایت پویا برای موتورهای جست‌وجو (SEO)"""
        from flask import Response
        from models import Bakery
        base = request.url_root.rstrip('/')
        urls = [f'{base}/', f'{base}/login']
        try:
            for b in Bakery.query.filter_by(is_active=True).all():
                urls.append(f'{base}/bakeries/{b.id}')
        except Exception:
            pass
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for u in urls:
            xml.append(f'<url><loc>{u}</loc></url>')
        xml.append('</urlset>')
        return Response('\n'.join(xml), mimetype='application/xml')

    @app.route('/google<path:google_file>')
    def google_verification(google_file):
        """تأییدیه Google Search Console —
        گوگل فایل را از ریشه سایت می‌خواهد: /googleXXXX.html
        ولی فایل فیزیکی در پوشه static است: static/googleXXXX.html
        پس google_file مثل 'XXXX.html' است و اسم کامل = 'google' + google_file"""
        import os as _os
        from flask import send_from_directory, abort
        filename = 'google' + google_file
        # جلوگیری از خروج از پوشه static (امنیت)
        if '/' in google_file or '..' in google_file:
            abort(404)
        file_path = _os.path.join(
            _os.path.dirname(_os.path.abspath(__file__)), 'static', filename
        )
        if _os.path.exists(file_path):
            return send_from_directory('static', filename, mimetype='text/html')
        abort(404)

    return app


app = create_app()


if __name__ == '__main__':
    print('=' * 52)
    print('  Bakery server is running')
    print('  On this laptop      : http://127.0.0.1:5000')
    for ip in get_local_ips():
        print(f'  Phones (hotspot/LAN): http://{ip}:5000')
    print('  Customer QR page    : http://127.0.0.1:5000/connect-qr')
    print('=' * 52)
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
