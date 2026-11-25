"""
سرویس ارسال کد تأیید از کانال‌های مختلف

کانال‌ها:
  - sms     : پیامک واقعی از طریق کاوه‌نگار (اگر KAVENEGAR_API_KEY تنظیم شده باشد)
              در غیر این صورت حالت آزمایشی (کد در sms_log.txt ذخیره می‌شود)
  - bale    : ارسال با بات بله    (متغیر محیطی BALE_BOT_TOKEN)
  - eitaa   : ارسال با بات ایتا   (متغیر محیطی EITAA_BOT_TOKEN)
  - rubika  : ارسال با بات روبیکا (متغیر محیطی RUBIKA_BOT_TOKEN)

نکته: بات‌ها فقط به کاربری می‌توانند پیام بدهند که یک بار ربات را Start کرده باشد.
"""
import os
import time
import requests

LOG_FILE = 'sms_log.txt'

MOCK_SMS = True  # در زمان ارسال بر اساس متغیرهای محیطی به‌روز می‌شود


def _env(name, default=''):
    return os.environ.get(name, default).strip()


def _mock():
    """اگر هیچ کلیدی تنظیم نشده باشد، حالت آزمایشی است"""
    return not (_env('KAVENEGAR_API_KEY') or _env('BALE_BOT_TOKEN') or
                _env('EITAA_BOT_TOKEN') or _env('RUBIKA_BOT_TOKEN'))


def _log(phone, text):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] to={phone} :: {text}\n"
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception:
        pass
    try:
        print(line.strip())
    except Exception:
        pass


def _send_sms(phone, text):
    """پیامک واقعی از طریق کاوه‌نگار؛ بدون کلید = حالت آزمایشی"""
    key = _env('KAVENEGAR_API_KEY')
    if not key:
        return True, 'sent_mock'
    try:
        params = {'receptor': phone, 'message': text}
        sender = _env('KAVENEGAR_SENDER')
        if sender:
            params['sender'] = sender
        resp = requests.get(
            f'https://api.kavenegar.com/v1/{key}/sms/send.json',
            params=params, timeout=10)
        data = resp.json()
        if data.get('return', {}).get('status') == 200:
            return True, 'sent'
        return False, 'خطا در ارسال پیامک: ' + str(data.get('return', {}).get('message'))
    except Exception:
        return False, 'خطا در اتصال به سرویس پیامک'


def _send_bale(phone, text):
    """ارسال با بات بله (API سازگار با تلگرام)"""
    token = _env('BALE_BOT_TOKEN')
    if not token:
        return False, 'ربات بله هنوز تنظیم نشده است'
    try:
        resp = requests.post(
            f'https://tapi.bale.ai/bot{token}/sendMessage',
            json={'chat_id': phone, 'text': text}, timeout=10)
        if resp.ok:
            return True, 'sent'
        # خطای 400/403 معمولاً یعنی کاربر ربات را استارت نکرده
        return False, 'کد ارسال نشد. ابتدا در بله وارد ربات شوید و دکمه Start را بزنید'
    except Exception:
        return False, 'خطا در اتصال به بله'


def _send_eitaa(phone, text):
    """ارسال با ایتایار (سرویس بات ایتا)"""
    token = _env('EITAA_BOT_TOKEN')
    if not token:
        return False, 'ربات ایتا هنوز تنظیم نشده است'
    try:
        resp = requests.post(
            f'https://eitaayar.ir/api/{token}/sendMessage',
            data={'chat_id': phone, 'text': text}, timeout=10)
        if resp.ok and resp.json().get('status', 200) == 200:
            return True, 'sent'
        return False, 'کد ارسال نشد. ابتدا در ایتا وارد ربات شوید و دکمه Start را بزنید'
    except Exception:
        return False, 'خطا در اتصال به ایتا'


def _send_rubika(phone, text):
    """ارسال با بات روبیکا (API رسمی v3 — مستندات rubika.ir/botapi)"""
    token = _env('RUBIKA_BOT_TOKEN')
    if not token:
        return False, 'ربات روبیکا هنوز تنظیم نشده است'
    try:
        # قالب رسمی: https://botapi.rubika.ir/v3/{token}/{method}
        resp = requests.post(
            f'https://botapi.rubika.ir/v3/{token}/sendMessage',
            json={'chat_id': phone, 'text': text}, timeout=10)
        data = resp.json()
        if resp.ok and data.get('status') == 'OK':
            return True, 'sent'
        # پیام خطای روبیکا یا کاربر استارت نکرده
        msg = data.get('status') or ''
        if msg in ('INVALID_INPUT', 'NOT_REGISTERED', 'FORBIDDEN', 'NOT_ACTIVE'):
            return False, 'NEEDS_START'
        return False, 'کد ارسال نشد (' + str(msg) + ')'
    except Exception:
        return False, 'خطا در اتصال به روبیکا'


_SENDERS = {
    'sms': _send_sms,
    'bale': _send_bale,
    'eitaa': _send_eitaa,
    'rubika': _send_rubika,
}

# ==================== BOT CONVERSATION SYSTEM ====================
import random, string as _str
from datetime import datetime, timedelta as _td

_BOT_CFG = {
    'rubika': {
        'token_env': 'RUBIKA_BOT_TOKEN',
        'base': 'https://botapi.rubika.ir/v3/{t}/',
        'send': 'sendMessage',
        'welcome': 'سلام! به ربات نانوبت خوش آمدید.\nشماره موبایل خود را بفرستید:',
        'name_ask': '✅ ثبت شد. نام و نام خانوادگی:',
        'done': '✅ ثبت شد! ورود به سایت: {link}\nکد پشتیبان: {code}',
    },
    'bale': {
        'token_env': 'BALE_BOT_TOKEN',
        'base': 'https://tapi.bale.ai/bot{t}/',
        'send': 'sendMessage',
        'welcome': 'سلام! شماره موبایل:',
        'name_ask': '✅ نام و نام خانوادگی:',
        'done': '✅ ورود: {link} | کد: {code}',
    },
    'eitaa': {
        'token_env': 'EITAA_BOT_TOKEN',
        'base': 'https://eitaayar.ir/api/{t}/',
        'send': 'sendMessage',
        'welcome': 'سلام! شماره موبایل:',
        'name_ask': '✅ نام:',
        'done': '✅ ورود: {link} | کد: {code}',
    },
}


def _make_token():
    return ''.join(random.choices(_str.ascii_letters + _str.digits, k=32))


def create_bot_session(phone, name, channel):
    from models import db, BotSession, User
    token = _make_token()
    expires = datetime.utcnow() + _td(minutes=10)
    bs = BotSession(token=token, phone=phone, name=name, channel=channel, used=False, expires_at=expires)
    user = User.query.filter_by(phone=phone).first()
    if user:
        bs.user_id = user.id
    db.session.add(bs)
    db.session.commit()
    return token


def _phone_norm(text):
    d = ''.join(c for c in (text or '') if c.isdigit())
    if len(d) == 11 and d.startswith('09'):
        return '0' + d[1:]
    if len(d) in (12, 13) and d.startswith('989'):
        return '0' + d[2:]
    return None


def _send_bot(channel, chat_id, text):
    """ارسال پیام از طریق بات در کانال مشخص — با مدیریت ریت‌لیمیت"""
    import os as _os, time as _time
    cfg = _BOT_CFG.get(channel)
    if not cfg:
        return False
    tkn = _os.environ.get(cfg['token_env'])
    if not tkn:
        return False
    try:
        url = cfg['base'].format(t=tkn) + cfg['send']
        resp = requests.post(url, json={'chat_id': str(chat_id), 'text': text}, timeout=15)
        if resp.ok:
            data = resp.json()
            # مدیریت ریت‌لیمیت روبیکا: کمی صبر و دوباره
            if channel == 'rubika' and data.get('status') == 'TOO_REQUESTS':
                _time.sleep(3)
                resp2 = requests.post(url, json={'chat_id': str(chat_id), 'text': text}, timeout=15)
                if resp2.ok:
                    return True
                return False
            return True
        return False
    except Exception:
        return False


# ==================== BOT POLLING (background threads) ====================
_bot_threads = {}
_bot_stops = {}


def _poll(channel, stop_ev, app=None):
    import time as _t, os as _os
    cfg = _BOT_CFG.get(channel)
    if not cfg:
        return
    tkn = _os.environ.get(cfg['token_env'])
    if not tkn:
        return
    url = cfg['base'].format(t=tkn) + 'getUpdates'
    last_offset = None
    while not stop_ev.is_set():
        try:
            payload = {'timeout': 0, 'limit': 20}
            if channel == 'rubika':
                payload = {}
                if last_offset:
                    payload['offset_id'] = last_offset
            else:
                # بله/ایتا: تلگرام‌سازگار — offset = آخرین update_id + ۱
                if last_offset is not None:
                    payload['offset'] = last_offset
            resp = requests.post(url, json=payload, timeout=25)
            if resp.ok:
                data = resp.json()
                # دو فرمت: روبیکا {status,data:{updates,next_offset_id}} — بله/ایتا {ok,result}
                if channel == 'rubika':
                    rdata = data.get('data') or {}
                    updates = rdata.get('updates') or []
                    # آفست رسمی روبیکا: next_offset_id از خود پاسخ
                    noff = rdata.get('next_offset_id')
                    if noff:
                        last_offset = noff
                else:
                    updates = data.get('result') or []
                if updates:
                    print(f'[poll:{channel}] {len(updates)} update(s)')
                for upd in updates:
                    # پردازش نیازمند app context است (دسترسی به دیتابیس)
                    try:
                        if app is not None:
                            with app.app_context():
                                _process_update(channel, upd)
                        else:
                            _process_update(channel, upd)
                    except Exception as pe:
                        import traceback as _tb
                        print(f'[poll:{channel}] process error: {pe}')
                        _tb.print_exc()
                    finally:
                        from models import db as _db
                        try:
                            _db.session.remove()
                        except Exception:
                            pass
                    if channel != 'rubika':
                        oid = upd.get('update_id')
                        if oid is not None:
                            last_offset = oid + 1
            else:
                print(f'[poll:{channel}] HTTP {resp.status_code}: {resp.text[:120]}')
        except Exception as e:
            print(f'[poll:{channel}] error: {e}')
        _t.sleep(5)


def _normalize_update(channel, upd):
    """هر دو فرمت (روبیکا / تلگرام‌سازگار) را به (chat_id, text) مشترک تبدیل می‌کند"""
    if channel == 'rubika':
        if upd.get('type') == 'StartedBot':
            return str(upd.get('chat_id') or ''), '/start'
        if upd.get('type') == 'NewMessage':
            return str(upd.get('chat_id') or ''), (upd.get('new_message') or {}).get('text') or ''
        return None, ''
    # بله / ایتا (تلگرام‌سازگار)
    msg = upd.get('message') or upd.get('edited_message') or {}
    chat = msg.get('chat') or {}
    cid = chat.get('id')
    return (str(cid) if cid is not None else None), msg.get('text') or ''


def _process_update(channel, upd):
    from models import db, BotUser
    chat_id, text = _normalize_update(channel, upd)
    if not chat_id:
        return
    text = (text or '').strip()

    # ریست / شروع
    if text in ('/start', 'شروع', '/restart', 'شروع مجدد'):
        bu = BotUser.query.filter_by(chat_id=str(chat_id), channel=channel).first()
        if bu:
            bu.step = 'none'
            bu.phone = None
            bu.name = None
            db.session.commit()
        cfg = _BOT_CFG.get(channel, {})
        _send_bot(channel, chat_id, cfg.get('welcome', 'سلام! شماره موبایل خود را بفرستید:'))
        return

    bu = BotUser.query.filter_by(chat_id=str(chat_id), channel=channel).first()
    if not bu:
        bu = BotUser(chat_id=str(chat_id), channel=channel)
        db.session.add(bu)

    cfg = _BOT_CFG.get(channel, {})

    if bu.step == 'none' or bu.step is None:
        phone = _phone_norm(text)
        if phone:
            bu.phone = phone
            bu.step = 'waiting_name'
            db.session.commit()
            _send_bot(channel, chat_id, cfg.get('name_ask', '✅ ثبت شد. نام و نام‌خانوادگی خود را بفرستید:'))
        else:
            _send_bot(channel, chat_id, cfg.get('welcome', 'شماره موبایل معتبر بفرستید:'))
        return

    if bu.step == 'waiting_name':
        name = text.strip()
        if len(name) < 2:
            _send_bot(channel, chat_id, 'نام معتبر بفرستید:')
            return
        bu.name = name
        bu.step = 'done'
        db.session.commit()
        code = str(random.randint(1000, 9999))
        token = create_bot_session(bu.phone, name, channel)
        _send_login_link(channel, chat_id, token, code)
        return

    # done: قبلاً ثبت شده
    _send_bot(channel, chat_id, 'شما قبلاً ثبت شده‌اید ✅ از لینک قبلی استفاده کنید یا /start را بفرستید.')


def start_bot_polling(app=None):
    """راه‌اندازی thread پس‌زمینه برای هر بات که توکن دارد"""
    import threading as _th
    import os as _os
    started = []
    for ch, cfg in _BOT_CFG.items():
        if not _os.environ.get(cfg['token_env']):
            continue
        if ch in _bot_threads and _bot_threads[ch].is_alive():
            continue
        ev = _th.Event()
        _bot_stops[ch] = ev
        t = _th.Thread(target=_poll, args=(ch, ev, app), daemon=True)
        t.start()
        _bot_threads[ch] = t
        started.append(ch)
    return started


def _send_login_link(channel, chat_id, token, code):
    site_url = os.environ.get('SITE_URL', 'https://bakery-webapp.onrender.com')
    link = site_url.rstrip('/') + f'/api/bot/login?token={token}'
    cfg = _BOT_CFG.get(channel, {})
    msg = (cfg.get('done') or '✅ ورود: {link} | کد: {code}').format(link=link, code=code)
    _send_bot(channel, chat_id, msg)

def send_otp(phone, code, channel='sms'):
    """ارسال کد تأیید از کانال انتخابی. خروجی: (موفقیت، پیام)"""
    global MOCK_SMS
    MOCK_SMS = _mock()
    text = f'کد تأیید ورود شما به نانوبت: {code}'
    _log(phone, f'[{channel}] {text}')
    if channel == 'sms' and MOCK_SMS:
        return True, 'sent_mock'
    sender = _SENDERS.get(channel, _send_sms)
    ok, msg = sender(phone, text)
    if ok:
        MOCK_SMS = False
    return ok, msg


def get_bot_url(channel):
    """لینک ورود به بات هر پیام‌رسان (برای راهنمایی کاربر به Start)"""
    urls = {
        'rubika': _env('RUBIKA_BOT_URL') or 'https://rubika.ir/nanobatbot',
        'bale': _env('BALE_BOT_URL') or 'https://ble.ir/nanobat_bot',
        'eitaa': _env('EITAA_BOT_URL') or '',
    }
    return urls.get(channel, '')
