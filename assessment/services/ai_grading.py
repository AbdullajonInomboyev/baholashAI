"""AI yordamida ochiq (yozma) javoblarni baholash.

Anthropic API'ga to'g'ridan-to'g'ri (stdlib urllib bilan) murojaat qiladi —
qo'shimcha paket shart emas. ANTHROPIC_API_KEY muhit o'zgaruvchisi bo'lmasa,
funksiya None qaytaradi (tizim eski qo'lda baholashga tushib qoladi, buzilmaydi).

Muhit o'zgaruvchilari:
    ANTHROPIC_API_KEY   — majburiy (bo'lmasa AI o'chiq)
    AI_GRADING_MODEL    — ixtiyoriy (default: claude-sonnet-4-6)
"""
import json
import os
import re
import urllib.request
import urllib.error

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"


def is_enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def grade_answer(question_text, student_answer, max_score=10, reference=""):
    """Bitta javobni baholaydi. -> {"score": float, "feedback": str} yoki None.

    feedback ichida NEGA shunday baholangani (izoh) bo'ladi.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    student_answer = (student_answer or "").strip()
    if not student_answer:
        return {"score": 0.0, "feedback": "Javob bo‘sh."}

    ref_part = f"\nNamunaviy/kutilgan javob (agar berilgan bo‘lsa):\n{reference}\n" if reference else ""
    prompt = (
        "Siz universitet imtihonini baholayotgan xolis va adolatli o‘qituvchisiz. "
        "Talabaning yozma javobini baholang.\n\n"
        f"SAVOL:\n{question_text}\n{ref_part}\n"
        f"TALABANING JAVOBI:\n{student_answer}\n\n"
        f"Javobni 0 dan {max_score} gача ballab baholang (to‘g‘rilik, to‘liqlik, aniqlik bo‘yicha). "
        "Izohda NEGA shunday baholaganingizni qisqa va aniq tushuntiring, kamchilik va yutuqlarni ayting. "
        "Faqat quyidagi JSON formatida javob bering, boshqa hech narsa yozmang:\n"
        '{"score": <son>, "feedback": "<o‘zbekcha qisqa izoh: nega shu ball>"}'
    )

    body = json.dumps({
        "model": os.environ.get("AI_GRADING_MODEL", DEFAULT_MODEL),
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None

    # javob matnini yig'amiz
    parts = data.get("content", [])
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    parsed = _extract_json(text)
    if not parsed or "score" not in parsed:
        return None
    try:
        score = float(parsed["score"])
    except (TypeError, ValueError):
        return None
    score = max(0.0, min(float(max_score), score))
    return {"score": round(score, 2), "feedback": str(parsed.get("feedback", "")).strip()[:500]}
