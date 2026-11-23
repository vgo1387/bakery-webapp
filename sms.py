"""
سرویس پیامک

در حالت آزمایشی (MOCK) کد تأیید ارسال واقعی نمی‌شود و در کنسول / فایل لاگ چاپ می‌شود
تا شما بتوانید فرایند لاگین را تست کنید.

برای اتصال به سرویس واقعی ایرانی (مثلاً Kavenegar):
  1. MOCK_SMS را به False تغییر دهید
  2. KAVENEGAR_API_KEY را پر کنید
  3. شماره ارسال‌کننده را ست کنید
"""
import time

MOCK_SMS = True                 # در حالت آزمایشی True بگذارید
KAVENEGAR_API_KEY = ''          # کلید API Kavenegar
SENDER = '1000000000'           # شماره یا خط ارسال

LOG_FILE = 'sms_log.txt'


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


def send_otp(phone, code):
    text = f"کد تأیید ورود شما به سامانه نانوایی: {code}"
    if MOCK_SMS:
        _log(phone, text)
        return True, 'sent_mock'
    try:
        # نمونه اتصال Kavenegar
        import requests
        resp = requests.get(
            'https://api.kavenegar.com/v1/{}/sms/send.json'.format(KAVENEGAR_API_KEY),
            params={'receptor': phone, 'message': text, 'sender': SENDER},
            timeout=10,
        )
        data = resp.json()
        if data.get('return', {}).get('status') == 200:
            return True, 'sent'
        return False, data.get('return', {}).get('message')
    except Exception as e:
        return False, str(e)
