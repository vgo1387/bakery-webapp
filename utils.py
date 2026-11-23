"""ابزارهای مشترک: تبدیل تاریخ شمسی + تولید QR کد تحویل"""
import io
from datetime import date, datetime, timedelta
import qrcode
import qrcode.image.svg

FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
JALALI_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
                 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
WEEKDAYS_FA = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه', 'یکشنبه']


def to_fa_digits(s):
    return str(s).translate(str.maketrans('0123456789', FA_DIGITS))


def gregorian_to_jalali(gy, gm, gd):
    """تبدیل میلادی به شمسی (الگوریتم استاندارد)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    g_day_no += g_d_m[gm2] + gd2
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + (j_day_no % 31)
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + ((j_day_no - 186) % 30)
    return jy, jm, jd


def jalali_str(d, with_weekday=False):
    """دریافت date میلادی → رشته شمسی خوانا، مثل: ۰۴ آذر ۱۴۰۴"""
    if d is None:
        return ''
    if isinstance(d, str):
        try:
            d = datetime.strptime(d, '%Y-%m-%d').date()
        except ValueError:
            return d
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    text = f'{to_fa_digits(f"{jd:02d}")} {JALALI_MONTHS[jm-1]} {to_fa_digits(jy)}'
    if with_weekday:
        text = WEEKDAYS_FA[d.weekday()] + ' ' + text
    return text


def qr_svg_base64(text):
    """تولید QR به صورت SVG و بازگشت data-URI برای قرارگیری مستقیم در HTML"""
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    buf = io.BytesIO()
    img.save(buf)
    import base64
    return 'data:image/svg+xml;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')

