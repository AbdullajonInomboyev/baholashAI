from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

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

        vice = self._user("zamdekan", "Alisher Karimov", active_password=True)
        UserRole.objects.get_or_create(user=vice, role=Role.VICE_DEAN, faculty=faculty)
        faculty.dean = vice
        faculty.save(update_fields=["dean"])

        head = self._user("mudir", "Dilnoza Rahimova", active_password=True)
        UserRole.objects.get_or_create(user=head, role=Role.DEPT_HEAD, department=department)
        department.head = head
        department.save(update_fields=["head"])
        # ko‘p rol: kafedra mudiri ayni vaqtda o‘qituvchi ham
        UserRole.objects.get_or_create(user=head, role=Role.TEACHER, department=department)

        teacher = self._user("oqituvchi", "Jamshid Qarabayev", active_password=True)
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

        # har xil turdagi resurslar (havola va matnli sahifa) — mavzuga bog'langan
        first_ta = assignments[0]
        topic = first_ta.department_course.course.topics.first()
        varied = [
            ("Foydali havola: rasmiy hujjatlar", Resource.Format.URL,
             {"url": "https://lex.uz", "kind": Resource.Kind.LITERATURE}),
            ("Video dars: kirish", Resource.Format.VIDEO,
             {"url": "https://www.youtube.com", "kind": Resource.Kind.VIDEO}),
            ("Qisqa konspekt (matn)", Resource.Format.PAGE,
             {"content": "Ushbu mavzu bo‘yicha asosiy tushunchalar, ta‘riflar va misollar.",
              "kind": Resource.Kind.LECTURE}),
        ]
        for title, fmt, extra in varied:
            res, created = Resource.objects.get_or_create(
                title=title, uploaded_by=teacher,
                defaults={"resource_format": fmt, "file": None, **extra},
            )
            ResourceLink.objects.get_or_create(
                resource=res, teacher_assignment=first_ta,
                defaults={"topic": topic})
            if created:
                ResourceReview.objects.get_or_create(
                    resource=res,
                    defaults={"ai_model": claude, "status": "completed",
                              "match_score": 90, "completeness_score": 85,
                              "feedback": "Namunaviy AI xulosasi."})

        # resurslarga namunaviy tasdiq holatlari
        res_all = list(Resource.objects.filter(uploaded_by=teacher).order_by("id"))
        statuses = [
            (Resource.ApprovalStatus.APPROVED, ""),
            (Resource.ApprovalStatus.PENDING, ""),
            (Resource.ApprovalStatus.REJECTED, "Sifat past — mavzular to‘liq yoritilmagan."),
        ]
        for idx, res in enumerate(res_all):
            st, note = statuses[idx % len(statuses)]
            res.approval_status = st
            res.review_note = note
            res.save(update_fields=["approval_status", "review_note"])

        # bir nechta talaba
        for i in range(1, 4):
            username = f"talaba{i}"
            student, created = User.objects.get_or_create(
                username=username, defaults={"full_name": f"Talaba {i}", "email": f"{username}@namdu.uz"}
            )
            if created:
                student.set_password("parol123")
                student.password_status = PasswordStatus.ACTIVE
                student.save()
            UserRole.objects.get_or_create(user=student, role=Role.STUDENT)
            StudentEnrollment.objects.get_or_create(
                student=student, academic_year=year,
                defaults={"direction": direction, "study_form": StudyForm.FULL_TIME,
                          "group_name": "ATT-25-01"},
            )

        # namunaviy akademik guruh + talabalarni biriktirish
        from academics.models import AcademicGroup
        group, _ = AcademicGroup.objects.get_or_create(
            direction=direction, name="ATT-25-01",
            defaults={"academic_year": year, "study_form": StudyForm.FULL_TIME,
                      "course": 1, "curator": teacher, "is_active": True},
        )
        for enr in StudentEnrollment.objects.filter(direction=direction, group__isnull=True):
            enr.group = group
            enr.save(update_fields=["group"])

        # zam dekandan mudirga namunaviy izoh
        from core.models import ReviewRemark
        vice = faculty.dean
        if vice and department.head:
            ReviewRemark.objects.get_or_create(
                author=vice, target=department.head, department=department,
                defaults={"message": "Amaliy materiallar to‘liq emas — to‘ldirib qo‘ying."},
            )

        self._seed_assignments(assignments)
        self._seed_quiz(assignments)
        self._seed_notifications()
        self._seed_rooms()
        self._seed_program()
        self._seed_schedule()

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
                      "description": "Berilgan mavzu bo'yicha amaliy ishni bajaring.",
                      "due_date": timezone.localdate() + timedelta(days=7)},
        )
        # rubrika (baholash mezonlari)
        from assessment.models import AssignmentCriterion
        if not assignment.criteria.exists():
            for i, (title, mx) in enumerate([
                ("Mazmun to'liqligi", 10), ("Tuzilish va mantiq", 10),
                ("Amaliy misollar", 10),
            ], start=1):
                AssignmentCriterion.objects.create(
                    assignment=assignment, title=title, max_points=mx, order=i)
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
            # rubrika bo'lsa — mezon bo'yicha o'qituvchi ballari (AI bilan bir xil qilib)
            for cs in first.criterion_scores.all():
                if cs.teacher_score is None:
                    cs.teacher_score = cs.ai_score
                    cs.save(update_fields=["teacher_score"])
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
        # mas'ul kafedra biriktiramiz (Yil -> Kafedra -> Yo'nalish ierarxiyasi uchun)
        if direction.department_id is None:
            dept = Department.objects.filter(faculty=faculty).first()
            if dept:
                direction.department = dept
                direction.save(update_fields=["department"])
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


    def _seed_quiz(self, assignments):
        """Namunaviy test + savollar + bitta talaba urinishi."""
        from assessment.models import Choice, Question, Quiz, QuizAnswer, QuizAttempt
        from assessment.services import quiz as quiz_service
        if not assignments:
            return
        ta = assignments[0]
        quiz, created = Quiz.objects.get_or_create(
            teacher_assignment=ta, title="Kirish testi",
            defaults={"description": "Fan bo‘yicha boshlang‘ich test.", "is_open": True,
                      "deadline": timezone.localdate() + timedelta(days=5)},
        )
        if created:
            q1 = Question.objects.create(quiz=quiz, text="2 + 2 = ?", kind=Question.Kind.SINGLE, points=1, order=1)
            Choice.objects.create(question=q1, text="3", order=1)
            Choice.objects.create(question=q1, text="4", is_correct=True, order=2)
            Choice.objects.create(question=q1, text="5", order=3)
            q2 = Question.objects.create(quiz=quiz, text="Python — dasturlash tili.", kind=Question.Kind.TRUE_FALSE, points=1, order=2)
            Choice.objects.create(question=q2, text="To‘g‘ri", is_correct=True, order=1)
            Choice.objects.create(question=q2, text="Noto‘g‘ri", order=2)
            q3 = Question.objects.create(quiz=quiz, text="HTML qisqartmasidagi birinchi harf nimani bildiradi?", kind=Question.Kind.SHORT, points=1, correct_text="HyperText", order=3)
        # talaba1 urinishi
        student = User.objects.filter(username="talaba1").first()
        if student and not QuizAttempt.objects.filter(quiz=quiz, student=student).exists():
            attempt = QuizAttempt.objects.create(quiz=quiz, student=student)
            for q in quiz.questions.all():
                a = QuizAnswer.objects.create(attempt=attempt, question=q)
                if q.kind == Question.Kind.SHORT:
                    a.text_answer = "HyperText"; a.save()
                else:
                    correct = q.choices.filter(is_correct=True).first()
                    if correct:
                        a.selected.set([correct])
            quiz_service.grade_attempt(attempt)


    def _seed_notifications(self):
        from core.models import Notification
        talaba = User.objects.filter(username="talaba1").first()
        if talaba and not Notification.objects.filter(user=talaba).exists():
            Notification.objects.create(user=talaba, message="Yangi topshiriq: 1-amaliy ish", url="/zamdekan/talaba/topshiriqlar/")
            Notification.objects.create(user=talaba, message="Yangi test: Kirish testi", url="/zamdekan/talaba/testlar/")
            Notification.objects.create(user=talaba, message="«1-amaliy ish» ishingizga baho qo\u2018yildi", url="/zamdekan/talaba/baholar/", is_read=True)


    def _seed_rooms(self):
        from schedule.models import Building, Room
        b1, _ = Building.objects.get_or_create(name="Bosh bino", defaults={"address": "Universitet ko‘chasi 1"})
        b2, _ = Building.objects.get_or_create(name="IT bino", defaults={"address": "Universitet ko‘chasi 3"})
        rooms = [
            (b1, "101", Room.Kind.LECTURE, 60, 1), (b1, "102", Room.Kind.PRACTICE, 30, 1),
            (b1, "201", Room.Kind.LECTURE, 80, 2),
            (b2, "A-1", Room.Kind.COMPUTER, 25, 1), (b2, "A-2", Room.Kind.LAB, 20, 1),
            (b2, "B-1", Room.Kind.COMPUTER, 25, 2),
        ]
        for b, name, kind, cap, floor in rooms:
            Room.objects.get_or_create(building=b, name=name,
                defaults={"kind": kind, "capacity": cap, "floor": floor})


    def _seed_program(self):
        from academics.models import Course, CourseLiterature, ControlType, Curriculum
        course = Course.objects.first()
        if course and not course.literature.exists():
            CourseLiterature.objects.create(course=course, title="Asosiy darslik", author="Karimov A.", year="2023", kind=CourseLiterature.Kind.MAIN, order=1)
            CourseLiterature.objects.create(course=course, title="Qo‘shimcha qo‘llanma", author="Rahimova D.", year="2022", kind=CourseLiterature.Kind.ADDITIONAL, order=2)
        if course and not course.control_types.exists():
            ControlType.objects.create(course=course, name="Oraliq nazorat", weight=30, order=1)
            ControlType.objects.create(course=course, name="Joriy nazorat", weight=30, order=2)
            ControlType.objects.create(course=course, name="Yakuniy nazorat", weight=40, order=3)
        cur = Curriculum.objects.first()
        if cur and not cur.is_approved:
            from django.utils import timezone as tz
            cur.is_approved = True; cur.approved_at = tz.now(); cur.save()


    def _seed_schedule(self):
        from datetime import time
        from schedule.models import TimeSlot, Lesson, Room
        from academics.models import Course, AcademicGroup, AcademicYear
        slots_def = [(1, time(8,30), time(9,50)), (2, time(10,0), time(11,20)),
                     (3, time(11,30), time(12,50)), (4, time(13,30), time(14,50)),
                     (5, time(15,0), time(16,20)), (6, time(16,30), time(17,50))]
        slots = []
        for order, st, en in slots_def:
            ts, _ = TimeSlot.objects.get_or_create(order=order, defaults={"start_time": st, "end_time": en})
            slots.append(ts)
        group = AcademicGroup.objects.first()
        year = AcademicYear.objects.filter(is_active=True).first() or AcademicYear.objects.first()
        rooms = list(Room.objects.all())
        courses = list(Course.objects.all()[:4])
        if not (group and year and courses and rooms):
            return
        if Lesson.objects.exists():
            return
        plan = [
            (courses[0], Lesson.WeekDay.MON, slots[0], Lesson.Kind.LECTURE),
            (courses[1], Lesson.WeekDay.MON, slots[1], Lesson.Kind.PRACTICE),
            (courses[2 % len(courses)], Lesson.WeekDay.TUE, slots[0], Lesson.Kind.LAB),
            (courses[3 % len(courses)], Lesson.WeekDay.WED, slots[1], Lesson.Kind.SEMINAR),
        ]
        for i, (course, day, slot, kind) in enumerate(plan):
            teacher = None
            ta = course.department_links.first() if hasattr(course, "department_links") else None
            from teaching.models import TeacherAssignment
            asg = TeacherAssignment.objects.filter(
                department_course__course=course, status=TeacherAssignment.Status.ACTIVE).first()
            teacher = asg.teacher if asg else group.curator
            if not teacher:
                continue
            les = Lesson.objects.create(academic_year=year, course=course, teacher=teacher,
                room=rooms[i % len(rooms)], timeslot=slot, week_day=day,
                week_type=Lesson.WeekType.ALL, kind=kind)
            les.groups.add(group)
