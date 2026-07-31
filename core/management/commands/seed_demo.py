from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import (
    AcademicYear, Department, Direction, Faculty, StudentEnrollment, StudyForm,
)
from accounts.models import PasswordStatus, Role, UserRole
from assessment.models import AIModel, AIModuleConfig, AssignmentType

User = get_user_model()

AI_MODELS = [
    ("GPT-4o", AIModel.Provider.OPENAI, "gpt-4o"),
    ("Gemini 1.5 Pro", AIModel.Provider.GOOGLE, "gemini-1.5-pro"),
    ("Claude 3.5 Sonnet", AIModel.Provider.ANTHROPIC, "claude-3-5-sonnet"),
]
ASSIGNMENT_TYPES = ["Test", "Yozma ish", "Amaliy topshiriq", "Kod"]
CONFIG = {"Test": "GPT-4o", "Yozma ish": "Gemini 1.5 Pro",
          "Amaliy topshiriq": "Claude 3.5 Sonnet", "Kod": "Claude 3.5 Sonnet"}


class Command(BaseCommand):
    help = "Tizimni sinab ko‘rish uchun namunaviy ma'lumot yaratadi."

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._user("admin", "Bosh administrator", superuser=True)
        UserRole.objects.get_or_create(user=admin, role=Role.ADMIN)

        faculty, _ = Faculty.objects.get_or_create(name="Axborot texnologiyalari fakulteti")
        department, _ = Department.objects.get_or_create(faculty=faculty, name="Axborot tizimlari kafedrasi")
        year, _ = AcademicYear.objects.get_or_create(faculty=faculty, title="2025-2026")

        vice = self._user("zamdekan", "Alisher Karimov")
        UserRole.objects.get_or_create(user=vice, role=Role.VICE_DEAN, faculty=faculty)
        faculty.dean = vice
        faculty.save(update_fields=["dean"])

        head = self._user("mudir", "Dilnoza Rahimova")
        UserRole.objects.get_or_create(user=head, role=Role.DEPT_HEAD, department=department)
        department.head = head
        department.save(update_fields=["head"])
        # ko‘p rol: kafedra mudiri ayni vaqtda o‘qituvchi ham
        UserRole.objects.get_or_create(user=head, role=Role.TEACHER, department=department)

        teacher = self._user("oqituvchi", "Jamshid Qarabayev")
        UserRole.objects.get_or_create(user=teacher, role=Role.TEACHER, department=department)

        student = self._user("talaba", "Sardor To‘xtayev", active_password=True)
        UserRole.objects.get_or_create(user=student, role=Role.STUDENT)
        direction = Direction.objects.filter(faculty=faculty).first()
        if direction:
            StudentEnrollment.objects.get_or_create(
                student=student, academic_year=year,
                defaults={"direction": direction, "study_form": StudyForm.FULL_TIME,
                          "group_name": "ATT-25-01"},
            )

        models = {}
        for name, provider, ident in AI_MODELS:
            models[name] = AIModel.objects.get_or_create(
                name=name, defaults={"provider": provider, "model_identifier": ident}
            )[0]
        for name in ASSIGNMENT_TYPES:
            at, _ = AssignmentType.objects.get_or_create(name=name)
            AIModuleConfig.objects.get_or_create(
                assignment_type=at, defaults={"ai_model": models[CONFIG[name]]}
            )

        self._seed_sample_curriculum(faculty, year)
        self._seed_teaching(faculty, department, teacher, year)

        self.stdout.write(self.style.SUCCESS("Namunaviy ma'lumot tayyor."))
        self.stdout.write("Kirish: admin/admin, zamdekan/parol123, mudir/parol123, "
                          "oqituvchi/parol123, talaba/parol123")

    def _user(self, username, full_name, *, superuser=False, active_password=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"full_name": full_name, "email": f"{username}@namdu.uz"},
        )
        if created:
            user.set_password("admin" if superuser else "parol123")
            user.password_status = (
                PasswordStatus.ACTIVE if (superuser or active_password) else PasswordStatus.TEMPORARY
            )
            user.is_staff = superuser
            user.is_superuser = superuser
            user.save()
        return user

    def _seed_teaching(self, faculty, department, teacher, year):
        """Import qilingan fanlar mavjud bo‘lsa — namunaviy o‘quv jarayoni."""
        from academics.models import Course, Direction, StudentEnrollment, StudyForm
        from accounts.models import Role, UserRole
        from assessment.models import AIModel
        from teaching.models import (
            DepartmentCourse, Resource, ResourceLink, ResourceReview, TeacherAssignment,
        )

        direction = Direction.objects.filter(faculty=faculty).first()
        if not direction:
            self.stdout.write("  (fanlar hali import qilinmagan — o‘quv jarayoni demo o‘tkazib yuborildi)")
            return

        courses = list(Course.objects.filter(
            curriculum__direction=direction, curriculum__study_form=StudyForm.FULL_TIME,
            is_elective=False
        ).order_by("code")[:6])
        if not courses:
            return

        admin = teacher  # granted_by uchun
        assignments = []
        for course in courses:
            link, _ = DepartmentCourse.objects.get_or_create(
                department=department, course=course, defaults={"assigned_by": admin}
            )
            ta, _ = TeacherAssignment.objects.get_or_create(
                department_course=link, teacher=teacher, defaults={"assigned_by": admin}
            )
            assignments.append(ta)

        claude = AIModel.objects.filter(provider=AIModel.Provider.ANTHROPIC).first()
        samples = [
            ("Ma‘ruza to‘plami — 1-8 mavzular", Resource.Kind.LECTURE, 92, 88, "completed"),
            ("Amaliy mashg‘ulot materiallari", Resource.Kind.PRACTICE, 71, 64, "completed"),
            ("Fan dasturi (ishchi variant)", Resource.Kind.SYLLABUS, None, None, "pending"),
        ]
        for i, (title, kind, match, complete, status) in enumerate(samples):
            res, created = Resource.objects.get_or_create(
                title=title, uploaded_by=teacher, defaults={"kind": kind, "file": "resources/demo.pdf"}
            )
            ResourceLink.objects.get_or_create(resource=res, teacher_assignment=assignments[i % len(assignments)])
            ResourceReview.objects.get_or_create(
                resource=res,
                defaults={"ai_model": claude, "status": status,
                          "match_score": match, "completeness_score": complete,
                          "feedback": "Namunaviy AI xulosasi."},
            )

        # bir nechta talaba
        for i in range(1, 4):
            username = f"talaba{i}"
            student, created = User.objects.get_or_create(
                username=username, defaults={"full_name": f"Talaba {i}", "email": f"{username}@namdu.uz"}
            )
            if created:
                student.set_password("parol123")
                student.save()
            UserRole.objects.get_or_create(user=student, role=Role.STUDENT)
            StudentEnrollment.objects.get_or_create(
                student=student, academic_year=year,
                defaults={"direction": direction, "study_form": StudyForm.FULL_TIME,
                          "group_name": "ATT-25-01"},
            )

        # zam dekandan mudirga namunaviy izoh
        from core.models import ReviewRemark
        vice = faculty.dean
        if vice and department.head:
            ReviewRemark.objects.get_or_create(
                author=vice, target=department.head, department=department,
                defaults={"message": "Amaliy materiallar to‘liq emas — to‘ldirib qo‘ying."},
            )

        self._seed_assignments(assignments)

    def _seed_assignments(self, assignments):
        """Namunaviy topshiriq + topshirilgan ishlar (o'qituvchi baholashi uchun)."""
        from assessment.models import Assignment, AssignmentType, Submission
        from assessment.services import ai

        if not assignments:
            return
        at = AssignmentType.objects.filter(name="Amaliy topshiriq").first() or AssignmentType.objects.first()
        if not at:
            return
        ta = assignments[0]
        assignment, _ = Assignment.objects.get_or_create(
            teacher_assignment=ta, title="1-amaliy ish",
            defaults={"assignment_type": at, "status": Assignment.Status.OPEN,
                      "description": "Berilgan mavzu bo'yicha amaliy ishni bajaring."},
        )
        for i in range(1, 4):
            student = User.objects.filter(username=f"talaba{i}").first()
            if not student:
                continue
            submission, created = Submission.objects.get_or_create(
                assignment=assignment, student=student,
                defaults={"text_answer": (
                    f"{student.full_name or student.username}ning javobi: mavzu bo‘yicha "
                    "asosiy tushunchalar, ta‘riflar va amaliy misollar keltirilgan."),
                    "status": Submission.Status.SUBMITTED},
            )
            if created:
                ai.evaluate_submission(submission)
        # bittasini o'qituvchi tasdiqlaydi — talaba "Baholarim" bo'sh qolmasin
        from assessment.models import TeacherReview
        first = assignment.submissions.first()
        if first and hasattr(first, "ai_evaluation") and not hasattr(first, "teacher_review"):
            TeacherReview.objects.get_or_create(
                submission=first,
                defaults={"teacher": ta.teacher, "final_score": first.ai_evaluation.score,
                          "status": TeacherReview.Status.CONFIRMED},
            )
            first.status = Submission.Status.TEACHER_REVIEWED
            first.save(update_fields=["status"])

    def _seed_sample_curriculum(self, faculty, year):
        """Excel import qilinmagan bo‘lsa — kichik namunaviy o‘quv reja yaratadi,
        shunda Fanlar/O‘quv yili bo‘limlari bo‘sh qolmaydi."""
        from academics.models import (
            Course, CourseSemester, Curriculum, Direction, Semester, StudyForm, SyllabusTopic,
        )

        if Course.objects.filter(curriculum__direction__faculty=faculty).exists():
            return  # allaqachon fanlar bor (import qilingan)

        direction, _ = Direction.objects.get_or_create(
            code="60610100",
            defaults={"name": "Axborot tizimlari va texnologiyalari", "faculty": faculty},
        )
        curriculum, _ = Curriculum.objects.get_or_create(
            direction=direction, academic_year=year, study_form=StudyForm.FULL_TIME
        )
        # (kod, nom, semestr, umumiy soat, tanlovmi)
        sample = [
            ("MAT101", "Oliy matematika", 1, 180, False),
            ("PRG101", "Dasturlash asoslari", 1, 180, False),
            ("PHY102", "Fizika", 1, 150, False),
            ("DB201", "Ma'lumotlar bazasi", 2, 150, False),
            ("WEB201", "Veb-texnologiyalar", 2, 120, False),
            ("OS202", "Operatsion tizimlar", 2, 120, False),
            ("NET301", "Kompyuter tarmoqlari", 3, 150, False),
            ("AI301", "Sun'iy intellekt asoslari", 3, 150, True),
            ("SE302", "Dasturiy injiniring", 3, 120, False),
        ]
        for code, name, sem_no, hours, elective in sample:
            course, _ = Course.objects.get_or_create(
                curriculum=curriculum, code=code,
                defaults={"name": name, "total_hours": hours, "is_elective": elective,
                          "lecture_hours": hours // 3, "practice_hours": hours // 3,
                          "independent_hours": hours - 2 * (hours // 3)},
            )
            semester, _ = Semester.objects.get_or_create(academic_year=year, number=sem_no)
            CourseSemester.objects.get_or_create(
                course=course, semester=semester,
                defaults={"credits": round(hours / 30, 2), "weekly_hours": 4},
            )
            for i in range(1, 4):
                SyllabusTopic.objects.get_or_create(
                    course=course, order=i,
                    defaults={"title": f"{name} — {i}-mavzu"},
                )
