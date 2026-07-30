"""AI baholash adapteri.

Dinamik model tanlash: topshiriq turiga qarab AIModuleConfig'dan model olinadi,
shu bilan tizim bironta AI ga qattiq bog‘lanmaydi. Hozircha baholovchi qism
MOCK (namunaviy) — haqiqiy provayder (OpenAI/Google/Anthropic) chaqiruvi
`_call_provider` ichiga qo‘yiladi.
"""
from decimal import Decimal

from assessment.models import AIEvaluation, AIModel, AIModuleConfig, Submission
from teaching.models import Resource, ResourceReview


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


def _call_provider(model, prompt):
    """TODO: haqiqiy provayder chaqiruvi shu yerda bo‘ladi.
    Hozircha mock javob qaytaradi."""
    raise NotImplementedError


def evaluate_submission(submission: Submission):
    """Topshirilgan ishni AI baholaydi (mock)."""
    model = model_for_assignment_type(submission.assignment.assignment_type)
    score = _pseudo(f"sub-{submission.pk}", 55, 96)
    feedback = (
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


def review_resource(resource: Resource):
    """Resurs yuklanganda AI mavzuga moslik va to‘liqlikni baholaydi (mock)."""
    model = AIModel.objects.filter(provider=AIModel.Provider.ANTHROPIC, is_active=True).first() \
        or AIModel.objects.filter(is_active=True).first()
    match = _pseudo(f"res-m-{resource.pk}", 60, 98)
    completeness = _pseudo(f"res-c-{resource.pk}", 55, 97)
    feedback = ("Namunaviy AI xulosasi: resurs fan dasturidagi mavzular bilan "
                "asosan mos; ayrim mavzular bo‘yicha material to‘ldirilishi mumkin.")
    ResourceReview.objects.update_or_create(
        resource=resource,
        defaults={"ai_model": model, "status": ResourceReview.Status.COMPLETED,
                  "match_score": Decimal(match), "completeness_score": Decimal(completeness),
                  "feedback": feedback},
    )
    return match, completeness
