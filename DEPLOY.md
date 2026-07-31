# GitHub va bepul serverga (Render) joylash

## 0. Talablar
- Git o‘rnatilgan bo‘lsin (https://git-scm.com/downloads).
- GitHub akkaunti (https://github.com).
- Render akkaunti (https://render.com) — GitHub bilan kirish mumkin.

## 1. GitHubʼda repozitoriya yaratish
1. GitHub → yuqori oʻngdagi **+** → **New repository**.
2. Nom: `oquv-ai` (masalan). **Private** ni tanlang (talaba maʼlumotlari uchun muhim).
3. README/gitignore qoʻshmang (bizda bor). **Create repository**.
4. Ochilgan sahifadagi repo manzilini nusxa oling: `https://github.com/FOYDALANUVCHI/oquv-ai.git`.

## 2. Loyihani GitHubʼga yuklash
Loyiha papkasida (bu zip ichida git allaqachon tayyor) terminal oching:

```bash
git remote add origin https://github.com/FOYDALANUVCHI/oquv-ai.git
git branch -M main
git push -u origin main
```

Agar “git allaqachon boshlangan emas” degan holat boʻlsa, avval:
```bash
git init
git add .
git commit -m "Dastlabki versiya"
```
soʻng yuqoridagi `remote add` va `push` ni bajaring.

> Eslatma: `.env`, `db.sqlite3`, `staticfiles/` GitHubʼga tushmaydi (`.gitignore` da).

## 3. Renderʼga deploy (bepul, blueprint bilan)
Loyihada `render.yaml` bor — bu web-server + bepul PostgreSQLʼni avtomatik sozlaydi.
1. Render → **New +** → **Blueprint**.
2. GitHub reponi ulang (`oquv-ai`).
3. Render `render.yaml` ni oʻqiydi va: web-servis + `oquv-ai-db` (PostgreSQL) yaratadi.
4. **Apply** bosing. Build boshlanadi (`build.sh`: paketlar → collectstatic → migrate → seed_demo).
5. Tugagach, manzil beriladi: `https://oquv-ai.onrender.com`.

Kirish:
- Admin: `.../admin/` → **admin / admin**
- Tizim: `.../hisob/kirish/` → **zamdekan / parol123**

## 4. Oʻquv reja importi (deploydan keyin)
Excel fayl repoda saqlanmaydi. Import qilish:
- **Eng oson:** tizimga zam dekan sifatida kiring → “Oʻquv yili va import” → Excelʼni yuklang.
- Yoki Render → Web Service → **Shell** → faylni yuklab, `python manage.py import_oquv_reja "fayl.xlsx"`.

## 5. Keyingi oʻzgarishlar (GitHub bilan)
Kodni oʻzgartirgach:
```bash
git add .
git commit -m "Nima oʻzgardi"
git push
```
Render har `push` da avtomatik qayta deploy qiladi.

## Muhim sozlamalar (Render env, blueprint avtomatik qoʻyadi)
- `DEBUG=False`
- `SECRET_KEY` — Render avtomatik generatsiya qiladi
- `ALLOWED_HOSTS=.onrender.com`
- `CSRF_TRUSTED_ORIGINS=https://*.onrender.com`
- `DATABASE_URL` — bazadan avtomatik ulanadi

## AI kalitini ulash (haqiqiy baholash)
Kalit qo‘shilmasa, AI **mock** (namunaviy) baho beradi — ilova ishlayveradi.
Haqiqiy AI baholash uchun Render’da web-servis → **Environment** → quyidagilardan
birini qo‘shing (qaysi provayder ishlatilsa):
- `ANTHROPIC_API_KEY` = sk-ant-...
- `OPENAI_API_KEY` = sk-...
- `GEMINI_API_KEY` = ...
So‘ng Admin → **AI modellar** da model ID to‘g‘ri ekanini tekshiring
(masalan `claude-3-5-sonnet-...`, `gpt-4o`, `gemini-1.5-pro`) va topshiriq
turiga bog‘lang (**AI modul sozlamalari**). Talaba **matn javob** yozib topshirsa,
AI aynan shu matnni baholaydi.

## Doimiy fayl saqlash (S3, ixtiyoriy)
Bepul serverda yuklangan fayllar deploy'da o'chadi. Doimiy saqlash uchun
S3-mos xizmat (AWS S3, Cloudflare R2, Backblaze B2) ulang: Render env'ga
qo'shing — `USE_S3=True`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME` (R2/B2 uchun `AWS_S3_ENDPOINT_URL`).
Kalitlar bo'lmasa tizim lokal saqlashda ishlayveradi.

## Eslatmalar
- Bepul rejada server 15 daqiqa harakatsizlikdan keyin “uxlaydi”; birinchi soʻrov 30–60 soniya sekin ochiladi.
- Fayllar (yuklangan resurs/rasm) bepul serverda vaqtincha saqlanadi (deployʼda oʻchishi mumkin). Doimiy saqlash uchun keyinroq S3/Cloudinary ulanadi.
- Google Fonts internetdan yuklanadi — muammosiz.
