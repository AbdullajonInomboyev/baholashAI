"""Test avtomatik baholash."""
from decimal import Decimal

from django.utils import timezone

from assessment.models import Question


def grade_attempt(attempt):
    total = 0
    earned = 0
    for q in attempt.quiz.questions.prefetch_related("choices").all():
        total += q.points
        ans = attempt.answers.filter(question=q).first()
        correct = False
        if ans:
            if q.kind == Question.Kind.SHORT:
                correct = bool(q.correct_text) and \
                    ans.text_answer.strip().lower() == q.correct_text.strip().lower()
            else:
                correct_ids = {c.id for c in q.choices.all() if c.is_correct}
                sel_ids = set(ans.selected.values_list("id", flat=True))
                correct = bool(correct_ids) and sel_ids == correct_ids
            if ans.is_correct != bool(correct):
                ans.is_correct = bool(correct)
                ans.save(update_fields=["is_correct"])
        if correct:
            earned += q.points
    score = round(earned / total * 100, 2) if total else 0
    attempt.score = Decimal(str(score))
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=["score", "submitted_at"])
    return score
