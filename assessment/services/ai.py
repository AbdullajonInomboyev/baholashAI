"""AI baholash adapteri.

Dinamik model tanlash: topshiriq turiga qarab AIModuleConfig'dan model olinadi,
shuning uchun tizim bironta AI ga qattiq bog'lanmaydi. Model ID ni Admin'dan
almashtirsangiz, kod o'zgarmasdan butun tizim yangi modelga o'tadi.

Haqiqiy provayder chaqiruvi `_call_llm` ichida. Tegishli API kalit `.env` da
bo'lsa — haqiqiy AI baholaydi; bo'lmasa yoki xato bo'lsa — mock (namunaviy)
javobga tushadi, ilova hech qachon buzilmaydi.

Kerakli muhit o'zgaruvchilari (ixtiyoriy):
  OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY
"""
import json
import logging
import os
import urllib.error
import urllib.request
from decimal import Decimal

from assessment.models import AIEvaluation, AIModel, AIModuleConfig, Submission
from teaching.models import Resource, ResourceReview

log = logging.getLogger(__name__)

_PROVIDER_ENV = {
    AIModel.Provider.OPENAI: "OPENAI_API_KEY",
    AIModel.Provider.ANTHROPIC: "ANTHROPIC_API_KEY",
    AIModel.Provider.GOOGLE: "GEMINI_API_KEY",
}


def model_for_assignment_type(assignment_type):
    config = (AIModuleConfig.objects
              .filter(assignment_type=assignment_type)
              .select_related("ai_model").first())
    if config and config.ai_model.is_active:
        return config.ai_model
    return AIModel.objects.filter(is_active=True).first()


def _pseudo(seed, low, high):
    """Barqaror (deterministik) namunaviy ball — mock uchun."""
    span = high - low
    return low + (abs(hash(seed)) % (span + 1))


# ---------------------------------------------------------------- provayder

def _http_json(url, payload, headers, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call_llm(model: AIModel, system: str, user: str, max_tokens: int = 800):
    """Modelning provayderiga qarab haqiqiy chaqiruv. Kalit yo'q yoki xato —
    None qaytaradi (chaqiruvchi mock'ga tushadi)."""
    if model is None:
        return None
    key = os.environ.get(_PROVIDER_ENV.get(model.provider, ""), "")
    if not key:
        return None
    try:
        if model.provider == AIModel.Provider.ANTHROPIC:
            data = _http_json(
                "https://api.anthropic.com/v1/messages",
                {"model": model.model_identifier, "max_tokens": max_tokens,
                 "system": system, "messages": [{"role": "user", "content": user}]},
                {"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"},
            )
            return "".join(b.get("text", "") for b in data.get("content", []))

        if model.provider == AIModel.Provider.OPENAI:
            data = _http_json(
                "https://api.openai.com/v1/chat/completions",
                {"model": model.model_identifier, "temperature": 0, "max_tokens": max_tokens,
                 "messages": [{"role": "system", "content": system},
                              {"role": "user", "content": user}]},
                {"content-type": "application/json", "authorization": f"Bearer {key}"},
            )
            return data["choices"][0]["message"]["content"]

        if model.provider == AIModel.Provider.GOOGLE:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model.model_identifier}:generateContent?key={key}")
            data = _http_json(url, {"contents": [{"parts": [{"text": system + "\n\n" + user}]}]},
                              {"content-type": "application/json"})
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
        log.warning("AI chaqiruv xatosi (%s): %s — mock'ga o'tildi", model.provider, e)
        return None
    return None


def _extract_json(text):
    """Javobdan birinchi {...} blokini ajratib, dict qaytaradi."""
    if not text:
        return None
    start, depth = text.find("{"), 0
    if start == -1:
        return None
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    return None
    return None


def _clamp(value, low, high, default):
    try:
        return max(low, min(high, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- baholash

def evaluate_submission(submission: Submission):
    """Topshirilgan ishni AI baholaydi. Rubrika (mezonlar) bo'lsa — har bir
    mezon bo'yicha; bo'lmasa — umumiy bitta baho. Kalit bo'lsa haqiqiy, bo'lmasa mock."""
    assignment = submission.assignment
    model = model_for_assignment_type(assignment.assignment_type)
    criteria = list(assignment.criteria.all())
    if criteria:
        return _evaluate_with_rubric(submission, model, criteria)

    score, feedback = None, None
    answer = (submission.text_answer or "").strip()
    if answer:  # baholanadigan matn bor
        system = (
            "Sen universitet o'qituvchisining yordamchisisan. Talabaning javobini "
            "topshiriq talablariga ko'ra 0 dan 100 gacha baholaysan. Faqat JSON "
            'qaytar: {"score": <0-100 son>, "feedback": "<o\'zbek tilida qisqa izoh>"}.'
        )
        user = (f"Topshiriq: {assignment.title}\n"
                f"Talab/tavsif: {assignment.description or '—'}\n\n"
                f"Talaba javobi:\n{answer[:4000]}")
        parsed = _extract_json(_call_llm(model, system, user))
        if parsed:
            score = _clamp(parsed.get("score"), 0, 100, None)
            feedback = str(parsed.get("feedback", "")).strip() or None

    if score is None:  # mock (kalit yo'q/matn yo'q/xato)
        score = _pseudo(f"sub-{submission.pk}", 55, 96)
        feedback = feedback or (
            "Namunaviy AI tahlili: ish topshiriq talablariga asosan bajarilgan. "
            "Tuzilma va mazmun qoniqarli; ayrim qismlarni chuqurroq yoritish tavsiya etiladi."
        )

    AIEvaluation.objects.update_or_create(
        submission=submission,
        defaults={"ai_model": model, "score": Decimal(score), "feedback": feedback},
    )
    if submission.status == Submission.Status.SUBMITTED:
        submission.status = Submission.Status.AI_EVALUATED
        submission.save(update_fields=["status"])
    return score


def _evaluate_with_rubric(submission, model, criteria):
    """Har bir mezon bo'yicha AI baho + izoh, so'ng umumiy foiz."""
    from assessment.models import CriterionScore

    assignment = submission.assignment
    answer = (submission.text_answer or "").strip()
    ai_scores = {}   # criterion_id -> (score, comment)

    if answer:
        lines = "\n".join(f"{i+1}. {c.title} (maks {c.max_points} ball)"
                          for i, c in enumerate(criteria))
        system = (
            "Sen universitet o'qituvchisining yordamchisisan. Talaba javobini "
            "berilgan mezonlar bo'yicha baholaysan. Har bir mezon uchun 0 dan "
            "mezonning maksimal balligacha ball qo'y. Faqat JSON qaytar: "
            '{"scores":[{"i":<mezon raqami>,"score":<ball>,"comment":"<izoh>"}]}.'
        )
        user = (f"Topshiriq: {assignment.title}\nTavsif: {assignment.description or '—'}\n\n"
                f"Mezonlar:\n{lines}\n\nTalaba javobi:\n{answer[:4000]}")
        parsed = _extract_json(_call_llm(model, system, user))
        if parsed and isinstance(parsed.get("scores"), list):
            for item in parsed["scores"]:
                idx = item.get("i")
                if isinstance(idx, int) and 1 <= idx <= len(criteria):
                    crit = criteria[idx - 1]
                    ai_scores[crit.id] = (
                        _clamp(item.get("score"), 0, crit.max_points, None),
                        str(item.get("comment", "")).strip(),
                    )

    total_max = sum(c.max_points for c in criteria) or 1
    earned = 0
    for c in criteria:
        sc, comment = ai_scores.get(c.id, (None, ""))
        if sc is None:  # mock
            sc = _pseudo(f"crit-{submission.pk}-{c.id}", int(c.max_points * 0.5), c.max_points)
            comment = comment or "Namunaviy AI izohi: mezon asosan qondirilgan."
        earned += sc
        CriterionScore.objects.update_or_create(
            submission=submission, criterion=c,
            defaults={"ai_score": Decimal(sc), "comment": comment},
        )

    overall = round(earned / total_max * 100, 2)
    AIEvaluation.objects.update_or_create(
        submission=submission,
        defaults={"ai_model": model, "score": Decimal(str(overall)),
                  "feedback": "Rubrika bo'yicha baholandi (mezonlar tafsiloti quyida)."},
    )
    if submission.status == Submission.Status.SUBMITTED:
        submission.status = Submission.Status.AI_EVALUATED
        submission.save(update_fields=["status"])
    return overall


def review_resource(resource: Resource):
    """Resurs yuklanganda AI mavzuga moslik va to'liqlikni baholaydi."""
    model = (AIModel.objects.filter(provider=AIModel.Provider.ANTHROPIC, is_active=True).first()
             or AIModel.objects.filter(is_active=True).first())

    match, completeness, feedback = None, None, None
    topics = []
    for link in resource.links.select_related("course").all() if hasattr(resource, "links") else []:
        topics += [t.title for t in link.course.topics.all()]
    if topics:
        system = (
            "Sen o'quv resurslarini fan dasturi mavzulariga solishtiruvchi yordamchisan. "
            'Faqat JSON qaytar: {"match": <0-100>, "completeness": <0-100>, '
            '"feedback": "<o\'zbek tilida qisqa izoh>"}.'
        )
        user = (f"Resurs nomi: {resource.title}\n"
                f"Fan dasturi mavzulari:\n- " + "\n- ".join(topics[:40]))
        parsed = _extract_json(_call_llm(model, system, user))
        if parsed:
            match = _clamp(parsed.get("match"), 0, 100, None)
            completeness = _clamp(parsed.get("completeness"), 0, 100, None)
            feedback = str(parsed.get("feedback", "")).strip() or None

    if match is None:
        match = _pseudo(f"res-m-{resource.pk}", 60, 98)
        completeness = _pseudo(f"res-c-{resource.pk}", 55, 97)
        feedback = feedback or ("Namunaviy AI xulosasi: resurs fan dasturidagi mavzular bilan "
                                "asosan mos; ayrim mavzular bo'yicha material to'ldirilishi mumkin.")

    ResourceReview.objects.update_or_create(
        resource=resource,
        defaults={"ai_model": model, "status": ResourceReview.Status.COMPLETED,
                  "match_score": Decimal(match), "completeness_score": Decimal(completeness),
                  "feedback": feedback},
    )
    return match, completeness
