// ---------- State ----------
let bakeries = [];
let userLocation = null;
let selectedBakeryId = null;

// ---------- Helpers ----------
function toFa(n) {
    return String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
}

function formatPrice(n) {
    return toFa(n.toLocaleString('en-US'));
}

function haversine(lat1, lng1, lat2, lng2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLng/2)**2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function distanceText(b) {
    if (!userLocation) return '';
    const km = haversine(userLocation.lat, userLocation.lng, b.latitude, b.longitude);
    return km < 1 ? toFa(Math.round(km * 1000)) + ' متر' : toFa(km.toFixed(1)) + ' کیلومتر';
}

function applyFilters() {
    const type = document.getElementById('filterType').value;
    const open = document.getElementById('filterOpen').value;
    const cap = document.getElementById('filterCapacity').value;

    return bakeries.filter(b => {
        if (type !== 'all' && b.bakery_type !== type) return false;
        if (open === 'open' && !b.is_active) return false;
        if (open === 'closed' && b.is_active) return false;
        if (cap !== 'all') {
            const hasCap = b._remaining > 0;
            if (cap === 'available' && !hasCap) return false;
            if (cap === 'full' && hasCap) return false;
        }
        return true;
    });
}

// ---------- Render List ----------
function renderList() {
    const list = document.getElementById('bakeriesList');
    if (!list) return;
    const items = applyFilters();

    if (!items.length) {
        list.innerHTML = '<p class="no-results">نانوایی‌ای با این فیلترها یافت نشد.</p>';
        return;
    }

    list.innerHTML = items.map(b => {
        const todayOpen = b._open_today;
        const hasCap = b._remaining > 0;
        const badges = `
            <div class="card-badges">
                <span class="mini-badge ${todayOpen ? 'ok' : 'no'}">${todayOpen ? 'امروز باز' : 'امروز بسته'}</span>
                <span class="mini-badge ${hasCap ? 'ok' : 'no'}">${hasCap ? 'ظرفیت: ' + toFa(b._remaining) : 'ظرفیت تکمیل'}</span>
                ${b.accepting_reservations ? '' : '<span class="mini-badge no">پذیرش بسته</span>'}
            </div>`;
        return `
        <div class="bakery-card type-${b.bakery_type} ${todayOpen ? 'open-today' : 'closed-today'}" onclick="showDetail(${b.id})">
            <div class="card-top">
                <span class="bakery-name">${b.name}</span>
                <span class="type-badge badge-${b.bakery_type}">${b.bakery_type === 'share' ? 'سهمیه‌ای' : 'آزاد'}</span>
            </div>
            <div class="bakery-meta">
                <span>📍 ${b.address}</span>
                <span>💰 نان ${formatPrice(b.price_per_loaf)} تومان</span>
                ${b._distance ? `<span>📏 فاصله: ${b._distance}</span>` : ''}
            </div>
            ${badges}
        </div>`;
    }).join('');
}

// ---------- Load ----------
async function loadBakeries() {
    try {
        const res = await fetch('/api/bakeries');
        bakeries = await res.json();
        const today = new Date().toISOString().split('T')[0];

        // ظرفیت و وضعیت امروز هر نانوایی
        await Promise.all(bakeries.map(async b => {
            try {
                const r = await fetch(`/api/bakeries/${b.id}/capacity?date=${today}`);
                const cap = await r.json();
                b._remaining = cap.remaining || 0;
                b._open_today = cap.available || b.is_active;
            } catch (e) {
                b._remaining = 0;
                b._open_today = b.is_active;
            }
        }));

        sortBakeries();
        renderList();
        drawMarkers();
    } catch (e) {
        console.error('خطا در بارگذاری نانوایی‌ها:', e);
    }
}

function sortBakeries() {
    if (userLocation) {
        bakeries.forEach(b => {
            b._distKm = haversine(userLocation.lat, userLocation.lng, b.latitude, b.longitude);
            b._distance = distanceText(b);
        });
        bakeries.sort((a, b) => a._distKm - b._distKm);
    }
    renderList();
}

// ---------- Routing helpers (مسیریابی + آیکون مشترک نقشه) ----------
window.TILE_URL = window.TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

// آیکون 📍 با CSS — بدون نیاز به فایل تصویر (رفع مشکل لود نشدن مارکر)
window.pinIcon = function (size) {
    const s = size || 34;
    return L.divIcon({
        className: '',
        html: `<div class="pin-emoji" style="font-size:${s}px;line-height:${s}px">📍</div>`,
        iconSize: [s, s],
        iconAnchor: [s / 2, s - 3],
        popupAnchor: [0, -(s - 10)]
    });
};

// منوی انتخاب برنامه مسیریابی: گوگل مپ / نشان / بلد
window.openRoutePicker = function (lat, lng, name) {
    let menu = document.getElementById('routePicker');
    if (!menu) {
        menu = document.createElement('div');
        menu.id = 'routePicker';
        menu.className = 'route-picker hidden';
        menu.innerHTML = `
            <div class="route-picker-box">
                <h3>🧭 مسیریابی با کدام برنامه؟</h3>
                <a class="route-btn gmap" target="_blank" rel="noopener">🔵 گوگل مپ</a>
                <a class="route-btn neshan" target="_blank" rel="noopener">🟢 نشان</a>
                <a class="route-btn balad" target="_blank" rel="noopener">🟡 بلد</a>
                <button class="route-cancel" type="button">بستن</button>
            </div>`;
        document.body.appendChild(menu);
        menu.addEventListener('click', e => {
            if (e.target === menu) menu.classList.add('hidden');
        });
        menu.querySelector('.route-cancel').addEventListener('click', () => menu.classList.add('hidden'));
    }
    menu.querySelector('.gmap').href = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
    menu.querySelector('.neshan').href = `https://neshan.org/maps/@${lat},${lng},17z,places`;
    menu.querySelector('.balad').href = `https://balad.ir/location?latitude=${lat}&longitude=${lng}&zoom=17`;
    menu.classList.remove('hidden');
};

// ---------- Geolocation ----------
function requestLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
        pos => {
            userLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
            setLocationMarker();
            sortBakeries();
        },
        () => console.log('دسترسی به موقعیت داده نشد')
    );
}

// ---------- Map ----------
let map = null;
let markers = [];

function initMapApp() {
    if (typeof L !== 'undefined') {
        map = L.map('map', { zoomControl: false }).setView([35.7448, 51.3753], 12);
        // زوم در سمت راست (هماهنگ با چیدمان RTL) زیر دکمه موقعیت قرار نمی‌گیرد
        L.control.zoom({ position: 'topright' }).addTo(map);
        L.tileLayer(window.TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
            maxZoom: 19,
            errorTileUrl: 'data:image/gif;base64,R0lGODlhAQABAIAAAPLtJgAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=='
        }).addTo(map);
        // بعد از رندر کامل، اندازه نقشه را دوباره محاسبه کن تا کاشی‌ها درست جای‌گیری شوند
        setTimeout(() => map.invalidateSize(), 200);
        window.addEventListener('resize', () => map.invalidateSize());
    } else {
        const el = document.getElementById('map');
        if (el) el.innerHTML = '<p style="padding:2rem;text-align:center;color:#666">نقشه بارگذاری نشد — اتصال اینترنت را بررسی کنید.</p>';
    }
    loadBakeries();
    requestLocation();

    ['filterType', 'filterOpen', 'filterCapacity'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', renderList);
    });

    const backBtn = document.getElementById('backToList');
    if (backBtn) backBtn.addEventListener('click', hideDetail);

    const locateBtn = document.getElementById('locateBtn');
    if (locateBtn) locateBtn.addEventListener('click', requestLocation);
}

function drawMarkers() {
    if (!map) return;
    markers.forEach(m => map.removeLayer(m));
    markers = [];
    bakeries.forEach(b => {
        const color = (b.id === selectedBakeryId) ? '#28a745' : '#dc3545';
        const icon = L.divIcon({
            className: '',
            html: `<div style="width:16px;height:16px;background:${color};border:2px solid white;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,0.4)"></div>`,
            iconSize: [16, 16],
            iconAnchor: [8, 8]
        });
        const m = L.marker([b.latitude, b.longitude], { icon }).addTo(map)
            .bindPopup(`<b>${b.name}</b><br><a href="/bakeries/${b.id}">مشاهده و رزرو</a>`);
        markers.push(m);
    });
}

function setLocationMarker() {
    if (!map || !userLocation) return;
    map.setView([userLocation.lat, userLocation.lng], 14);
    L.circleMarker([userLocation.lat, userLocation.lng], {
        radius: 8, color: '#0d6efd', fillColor: '#0d6efd', fillOpacity: 0.8
    }).addTo(map).bindPopup('موقعیت شما');
}


// ---------- Detail Sheet ----------
async function showDetail(id) {
    selectedBakeryId = id;
    drawMarkers();
    try {
        const res = await fetch('/api/bakeries/' + id);
        const b = await res.json();
        const todayOpen = b.is_active && b.accepting_reservations;
        const typeText = b.bakery_type === 'share' ? 'سهمیه‌ای' : 'آزاد';

        document.getElementById('bakeryDetailContent').innerHTML = `
            <div class="card-top">
                <span class="bakery-name" style="font-size:1.2rem">${b.name}</span>
                <span class="type-badge badge-${b.bakery_type}">${typeText}</span>
            </div>
            <div class="bakery-meta" style="margin:0.8rem 0">
                <span>📍 ${b.address}</span>
                <span>📞 ${b.phone || '-'}</span>
                <span>🕐 ${b.working_hours_start} تا ${b.working_hours_end}</span>
                <span>🍞 نان: ${formatPrice(b.price_per_loaf)} تومان</span>
                <span>👜 کیسه: ${formatPrice(b.price_per_bag)} تومان</span>
                ${b._distance ? `<span>📏 فاصله: ${b._distance}</span>` : ''}
                <span>${todayOpen ? '🟢 امروز باز است' : '🔴 امروز بسته است'}</span>
            </div>
            <a href="/bakeries/${b.id}/reserve" class="btn-primary btn-block">دریافت نوبت</a>
        `;
        document.getElementById('bakeryDetailSheet').classList.remove('hidden');
    } catch (e) {
        console.error(e);
    }
}

function hideDetail() {
    selectedBakeryId = null;
    document.getElementById('bakeryDetailSheet').classList.add('hidden');
    drawMarkers();
}

// ---------- Reserve Page ----------
async function checkCapacity() {
    const dateInput = document.getElementById('reservationDate');
    const msg = document.getElementById('capacityMsg');
    if (!dateInput || !dateInput.value || !msg) return;
    const bakeryId = window.location.pathname.split('/')[2];
    try {
        const res = await fetch(`/api/bakeries/${bakeryId}/capacity?date=${dateInput.value}`);
        const cap = await res.json();
        const submitBtn = document.getElementById('submitBtn');
        if (cap.available) {
            msg.textContent = `ظرفیت این روز: ${toFa(cap.remaining)} نوبت`;
            msg.className = 'capacity-msg ok';
            submitBtn.disabled = false;
        } else {
            const reasons = {
                holiday: 'این روز تعطیل است',
                closed_day: 'این روز جزو روزهای کاری نیست',
                capacity_full: 'ظرفیت این روز تکمیل شده است',
                inactive: 'نانوایی غیرفعال است',
                accepting_closed: 'نانوایی پذیرش نوبت را بسته است',
                capacity_closed: 'ظرفیت این روز تکمیل شده است',
            };
            msg.textContent = reasons[cap.reason] || 'امکان رزرو در این روز نیست';
            msg.className = 'capacity-msg no';
            submitBtn.disabled = true;
        }
    } catch (e) {
        console.error(e);
    }
}

function updateSummary() {
    const priceEl = document.getElementById('priceSummary');
    if (!priceEl) return;
    const loaves = parseInt(document.getElementById('loafCount').value) || 0;
    const bags = parseInt(document.getElementById('bagCount').value) || 0;
    const total = loaves * (window._pricePerLoaf || 0) + bags * (window._pricePerBag || 0);
    priceEl.innerHTML = `مبلغ کل: <strong>${formatPrice(total)}</strong> تومان`;
}

async function submitReservation(bakeryId) {
    const payload = {
        bakeryId: parseInt(bakeryId),
        date: document.getElementById('reservationDate').value,
        loafCount: parseInt(document.getElementById('loafCount').value),
        bagCount: parseInt(document.getElementById('bagCount').value) || 0,
        breadType: document.getElementById('breadType').value,
        userPhone: document.getElementById('userPhone').value.trim(),
    };
    const errEl = document.getElementById('errorMsg');
    const btn = document.getElementById('submitBtn');
    errEl.classList.add('hidden');
    btn.disabled = true;

    try {
        const res = await fetch('/api/reservations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            window.location.href = '/reservations/' + data.reservation.code;
        } else {
            errEl.textContent = data.error || 'خطا در ثبت رزرو';
            errEl.classList.remove('hidden');
            btn.disabled = false;
        }
    } catch (e) {
        errEl.textContent = 'خطای ارتباط با سرور';
        errEl.classList.remove('hidden');
        btn.disabled = false;
    }
}
