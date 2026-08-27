FROM python:3.12-slim

# libwmf-bin: MathType (WMF) formulalarni PNG ga o'tkazish uchun (wmf2gd).
# Bu paket YENGIL (bir necha MB) — LibreOffice kabi og'ir emas.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libwmf-bin \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Statik fayllarni yig'amiz (build vaqtida; DB kerak emas)
RUN SECRET_KEY=build-only DEBUG=False python manage.py collectstatic --no-input

RUN chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]
