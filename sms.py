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
    """ارسال با بات روبیکا (API رسمی محدود است؛ در صورت تنظیم توکن تلاش می‌شود)"""
    token = _env('RUBIKA_BOT_TOKEN')
    if not token:
        return False, 'ربات روبیکا هنوز تنظیم نشده است'
    try:
        resp = requests.post(
            f'https://botapi.rubika.ir/v3/bots/{token}/sendMessage',
            json={'chat_id': phone, 'text': text}, timeout=10)
        if resp.ok:
            return True, 'sent'
        return False, 'کد ارسال نشد. ابتدا در روبیکا وارد ربات شوید و دکمه Start را بزنید'
    except Exception:
        return False, 'خطا در اتصال به روبیکا'


_SENDERS = {
    'sms': _send_sms,
    'bale': _send_bale,
    'eitaa': _send_eitaa,
    'rubika': _send_rubika,
}


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
