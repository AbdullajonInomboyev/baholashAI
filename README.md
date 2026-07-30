# O‘quv AI platformasi

Universitet o‘quv jarayoni va AI yordamidagi baholash tizimi. Django + PostgreSQL.

## Rollar

Admin, Zam dekan, Kafedra mudiri, O‘qituvchi, Talaba. Bitta foydalanuvchi bir
nechta rolga ega bo‘lishi mumkin — har bir rol fakultet yoki kafedra doirasiga
biriktiriladi (`accounts.UserRole`).

## Loyiha tuzilmasi

| Ilova | Vazifasi |
|-------|----------|
| `accounts` | Foydalanuvchilar, rollar (multi-rol, scope), parol holati |
| `academics` | Fakultet, kafedra, yo‘nalish, o‘quv yili, **o‘quv reja (Curriculum)**, semestr, fan, import, talaba |
| `teaching` | Fanni kafedra/o‘qituvchiga biriktirish, resurslar, resurs AI tahlili |
| `assessment` | Topshiriq turlari, AI modellar, dinamik AI sozlamalari, topshiriq–baholash tsikli |
| `core` | Hisobotlar, to‘g‘irlash izohlari, audit jurnali |
| `portal` | Rol panellari (hozircha Zam dekan to‘liq): UI, formalar, import/export |

## Ishga tushirish (dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py import_oquv_reja "yol/25-26 ....xlsx"   # o'quv reja
python manage.py seed_demo          # foydalanuvchilar, AI sozlamalari, demo o'quv jarayoni
python manage.py runserver
```

Kirish: `admin/admin`, `zamdekan/parol123`, `mudir/parol123`,
`oqituvchi/parol123`, `talaba/parol123`.

## O‘quv reja (Curriculum)

Fan to‘g‘ridan-to‘g‘ri yo‘nalishga emas, **o‘quv rejaga** bog‘lanadi.
O‘quv reja = *yo‘nalish × o‘quv yili × ta‘lim shakli*. Shu sabab bir xil
yo‘nalish har o‘quv yilida alohida rejaga (alohida fanlar to‘plamiga) ega
bo‘ladi va yangi yil importi eskisini o‘chirmaydi. Navigatsiya:
Fakultet → O‘quv yili → Yo‘nalish → Semestr → Fan.

## O‘quv reja importi

`import_oquv_reja` buyrug‘i O‘quv reja Excel shablonini o‘qiydi: yo‘nalish
kodini (S6), fan kodi/nomi/soatlarini, semestr taqsimotini ajratadi va
kreditni `soat / 30` formulasi bo‘yicha hisoblaydi. Uch varaq — uch ta‘lim
shakli (kunduzgi/kechki/masofaviy) — alohida import qilinadi. Takroriy fan
kodlari import jurnaliga yozilib, qo‘lda tuzatish uchun belgilanadi.

```bash
python manage.py import_oquv_reja fayl.xlsx --form kunduzgi --year 2025-2026
```

## Zam dekan paneli

`zamdekan/parol123` bilan kirilганda `/zamdekan/` paneli ochiladi. To‘liq
ishlaydigan bo‘limlar:

- **Kafedralar** — yaratish/tahrirlash/o‘chirish, mudir tayinlash.
- **Yo‘nalishlar** — yaratish/tahrirlash.
- **O‘quv yili va import** — yil ochish; O‘quv reja Excel'ini yuklab import
  qilish (semestr/fan/soat/kredit avtomatik); fanlarni semestr bo‘yicha ko‘rish.
- **Fanlar** — filtr, qo‘lda qo‘shish/tahrirlash, kafedraga biriktirish.
- **Talabalar** — Excel import va export, namunaviy shablon.
- **Hisobotlar** — kafedra/fakultet hisobotini Excel'ga yuklab olish; kafedra
  mudiriga «to‘g‘irla» izohini yuborish.
- **Parol tiklash** — o‘zidan past lavozimdagilarga vaqtinchalik parol.

## Kafedra mudiri paneli

`mudir/parol123` bilan kirilганда `/zamdekan/kafedra/` ochiladi:

- **Fanlar va o‘qituvchilar** — kafedra fanlari; istalgan fakultet fanini
  qidirib biriktirish; bitta fanga bir nechta o‘qituvchi biriktirish, olib tashlash.
- **Resurs sifati (AI)** — o‘qituvchilar yuklagan resurslarning mavzuga mosligi
  va to‘liqligi; o‘qituvchi/fan bo‘yicha va «<80% moslik» bo‘yicha drill-down;
  har bir resurs bo‘yicha batafsil AI xulosasi.
- **Izohlar** — zam dekandan kelgan «to‘g‘irla» izohlari; «hal qilindi» belgilash.

## O‘qituvchi va Talaba panellari

`oqituvchi/parol123` → `/zamdekan/oqituvchi/`:
- **Fanlarim va topshiriqlar** — biriktirilgan fanlar; topshiriq yaratish/tahrirlash/o‘chirish
  (turi tanlanadi, uni qaysi AI baholashi Admin sozlamasidan dinamik olinadi).
- **Ishlar** — topshirilgan ishlar; AI bahosini tasdiqlash yoki yakuniy bahoni qo‘lda o‘zgartirish.
- **Resurslar** — fayl yuklash, bir nechta fanga biriktirish; yuklanishi bilan AI moslik/to‘liqlik tahlili.

`talaba1/parol123` → `/zamdekan/talaba/`:
- **Topshiriqlarim** — o‘z yo‘nalishi/shakliga mos topshiriqlar; fayl topshirish (AI darhol baholaydi).
- **Baholarim** — AI bahosi (dastlabki) va o‘qituvchi tasdiqlagan yakuniy baho.

## AI adapteri

`assessment/services/ai.py` dinamik model tanlaydi (topshiriq turi → `AIModuleConfig` → model),
shu bilan tizim bironta AI ga qattiq bog‘lanmaydi. Hozircha baholovchi qism namunaviy (mock);
haqiqiy provayder (OpenAI/Google/Anthropic) chaqiruvi `_call_provider` ichiga qo‘yiladi.

## PostgreSQL (prod)

`.env` da `DATABASE_URL` ni ko‘rsating; qolgani o‘zgarmaydi.
