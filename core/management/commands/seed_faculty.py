"""Bitta fakultetni TO'LIQ demo ma'lumot bilan to'ldiradi:
kafedralar, yo'nalishlar, o'quv reja + fanlar, o'qituvchilar, guruhlar,
talabalar (HEMIS profillari bilan) va barcha biriktiruvlar.

Ishlatish:
    python manage.py seed_faculty
    python manage.py seed_faculty --students 16 --reset
Idempotent: qayta ishga tushsa dublikat yaratmaydi.
"""
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

User = get_user_model()

FIRST_M = ["Abror", "Bekzod", "Doston", "Eldor", "Farrux", "G'ayrat", "Hasan", "Islom",
           "Jasur", "Kamron", "Laziz", "Muhammad", "Nodir", "Otabek", "Sardor", "Temur",
           "Ulug'bek", "Shohruh", "Javohir", "Sanjar"]
FIRST_F = ["Aziza", "Barno", "Dilnoza", "Feruza", "Gulnora", "Hilola", "Iroda", "Kamola",
           "Laylo", "Madina", "Nilufar", "Ozoda", "Robiya", "Sevara", "Zarina", "Malika",
           "Nozima", "Charos", "Shahnoza", "Dildora"]
LAST = ["Aliyev", "Bektemirov", "Davronov", "Ergashev", "Fayzullayev", "G'aniyev",
        "Hakimov", "Islomov", "Jo'rayev", "Karimov", "Latipov", "Mirzayev", "Nazarov",
        "Olimov", "Po'latov", "Qodirov", "Rahimov", "Saidov", "To'xtayev", "Usmonov",
        "Xolmatov", "Yusupov", "Zoirov", "Abdullayev", "Ismoilov"]

SUBJECTS = [
    ("BB101", "Iqtisodiyot nazariyasi", 1), ("BB102", "Menejment asoslari", 1),
    ("BB103", "Oliy matematika", 1), ("BB104", "Axborot texnologiyalari", 1),
    ("BB201", "Mikroiqtisodiyot", 2), ("BB202", "Marketing asoslari", 2),
    ("BB203", "Buxgalteriya hisobi", 2), ("BB204", "Huquqshunoslik asoslari", 2),
    ("BB301", "Makroiqtisodiyot", 3), ("BB302", "Moliya", 3),
    ("BB303", "Statistika", 3), ("BB304", "Tadbirkorlik asoslari", 4),
    ("BB401", "Ekonometrika", 5), ("BB402", "Inson resurslarini boshqarish", 5),
    ("BB403", "Xalqaro biznes", 6), ("BB404", "Soliqlar va soliqqa tortish", 6),
    ("BB501", "Strategik menejment", 7), ("BB502", "Korporativ moliya", 7),
    ("BB503", "Audit", 8), ("BB504", "Raqamli iqtisodiyot", 8),
]

DEPARTMENTS = [
    "Menejment kafedrasi",
    "Marketing kafedrasi",
    "Moliya va soliqlar kafedrasi",
    "Buxgalteriya hisobi va audit kafedrasi",
]

DIRECTIONS = [
    ("60610800", "Biznes boshqaruvi (menejment)", "BB", 0),
    ("60411800", "Marketing", "MK", 1),
    ("60411100", "Moliya va moliyaviy texnologiyalar", "ML", 2),
]


class Command(BaseCommand):
    help = "Bitta fakultetni to'liq demo ma'lumot bilan to'ldiradi."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=14,
                            help="Har guruhdagi talabalar soni (default 14)")
        parser.add_argument("--faculty", type=str, default="Biznes boshqaruvi fakulteti")
        parser.add_argument("--reset", action="store_true",
                            help="Avval shu fakultet demo ma'lumotini o'chirib, qaytadan yaratadi")

    @transaction.atomic
    def handle(self, *args, **opt):
        from academics.models import (
            AcademicGroup, AcademicYear, Course, CourseSemester, Curriculum,
            Department, Direction, Faculty, Semester, StudentEnrollment, StudyForm,
        )
        from accounts.models import PasswordStatus, Role, StudentProfile, UserRole
        from teaching.models import DepartmentCourse, TeacherAssignment

        random.seed(42)
        fac_name = opt["faculty"]
        per_group = opt["students"]

        if opt["reset"]:
            fac = Faculty.objects.filter(name=fac_name).first()
            if fac:
                StudentEnrollment.objects.filter(direction__faculty=fac).delete()
                Faculty.objects.filter(pk=fac.pk).delete()
                self.stdout.write(self.style.WARNING(f"'{fac_name}' o'chirildi (reset)."))

        faculty, _ = Faculty.objects.get_or_create(name=fac_name)
        year, _ = AcademicYear.objects.get_or_create(faculty=faculty, title="2025-2026")
        semesters = {n: Semester.objects.get_or_create(academic_year=year, number=n)[0]
                     for n in range(1, 9)}

        # --- Kafedralar ---
        depts = []
        for dn in DEPARTMENTS:
            d, _ = Department.objects.get_or_create(faculty=faculty, name=dn)
            depts.append(d)

        # --- Dekanat (vice-dean) hisobi ---
        vice = self._user("zamdekan_bb", "SODIQOV BAHODIR AKMAL O'G'LI")
        UserRole.objects.get_or_create(user=vice, role=Role.VICE_DEAN, faculty=faculty)
        if not faculty.dean:
            faculty.dean = vice
            faculty.save(update_fields=["dean"])

        # --- Yo'nalishlar ---
        directions = []
        for code, dname, prefix, dept_idx in DIRECTIONS:
            direction, _ = Direction.objects.get_or_create(
                code=code, defaults={"faculty": faculty, "name": dname})
            if direction.faculty_id != faculty.id:
                direction.faculty = faculty
            direction.name = dname
            direction.department = depts[dept_idx]
            direction.save()
            directions.append((direction, prefix, depts[dept_idx]))

        # --- O'qituvchilar (kafedralarga) ---
        teachers = []
        for i in range(8):
            dept = depts[i % len(depts)]
            fn = random.choice(FIRST_M); ln = random.choice(LAST)
            t = self._user(f"oqituvchi_bb{i+1}", f"{ln.upper()} {fn.upper()}")
            UserRole.objects.get_or_create(user=t, role=Role.TEACHER, department=dept)
            teachers.append((t, dept))
        # Har kafedraga mudir (dept head)
        for k, dept in enumerate(depts):
            head_teacher = teachers[k][0]
            UserRole.objects.get_or_create(user=head_teacher, role=Role.DEPT_HEAD, department=dept)
            if not dept.head:
                dept.head = head_teacher
                dept.save(update_fields=["head"])

        # --- O'quv reja + fanlar (har yo'nalish uchun) ---
        total_courses = 0
        for direction, prefix, dept in directions:
            curriculum, _ = Curriculum.objects.get_or_create(
                direction=direction, academic_year=year, study_form=StudyForm.FULL_TIME,
                defaults={"is_approved": True, "approved_at": timezone.now()})
            if not curriculum.is_approved:
                curriculum.is_approved = True
                curriculum.approved_at = timezone.now()
                curriculum.save(update_fields=["is_approved", "approved_at"])
            for code, cname, sem_no in SUBJECTS:
                course, created = Course.objects.get_or_create(
                    curriculum=curriculum, code=f"{prefix}-{code}",
                    defaults={"name": cname, "credit": Decimal("5.00"),
                              "total_hours": 150, "lecture_hours": 30,
                              "practice_hours": 30, "independent_hours": 90})
                total_courses += 1 if created else 0
                CourseSemester.objects.get_or_create(
                    course=course, semester=semesters[sem_no],
                    defaults={"credits": Decimal("5.00"), "weekly_hours": 4})
                # kafedra-fan + o'qituvchi biriktiruvi
                dep_course, _ = DepartmentCourse.objects.get_or_create(
                    department=dept, course=course, defaults={"assigned_by": vice})
                teacher = random.choice([t for t, d in teachers if d == dept] or [teachers[0][0]])
                TeacherAssignment.objects.get_or_create(
                    department_course=dep_course, teacher=teacher,
                    defaults={"assigned_by": vice, "status": TeacherAssignment.Status.ACTIVE})

        # --- Guruhlar + talabalar ---
        n_students = 0
        n_groups = 0
        for direction, prefix, dept in directions:
            for course_no in range(1, 5):                 # 1-4 kurs
                yy = 25 - (course_no - 1)                  # qabul yili (2 raqam)
                group_name = f"{prefix}-{yy:02d}-01"
                group, _ = AcademicGroup.objects.get_or_create(
                    direction=direction, name=group_name,
                    defaults={"academic_year": year, "course": course_no,
                              "study_form": StudyForm.FULL_TIME, "is_active": True})
                n_groups += 1
                for s in range(per_group):
                    is_female = random.random() < 0.45
                    fn = random.choice(FIRST_F if is_female else FIRST_M)
                    ln = random.choice(LAST)
                    suffix = "QIZI" if is_female else "O'G'LI"
                    full = f"{ln.upper()} {fn.upper()} {random.choice(LAST).upper()} {suffix}"
                    uname = f"st_{prefix.lower()}{yy:02d}_{s+1:02d}"
                    stu, created = User.objects.get_or_create(
                        username=uname, defaults={"full_name": full})
                    if created:
                        stu.set_password("parol123")
                        stu.password_status = PasswordStatus.ACTIVE
                        stu.save()
                        n_students += 1
                    UserRole.objects.get_or_create(user=stu, role=Role.STUDENT)
                    StudentEnrollment.objects.get_or_create(
                        student=stu, academic_year=year, direction=direction,
                        defaults={"study_form": StudyForm.FULL_TIME,
                                  "group_name": group_name, "group": group,
                                  "status": StudentEnrollment.Status.ACTIVE})
                    # HEMIS profil (ma'lumotlar to'liq ko'rinsin)
                    prof, _ = StudentProfile.objects.get_or_create(user=stu)
                    prof.student_id = prof.student_id or get_random_string(12, "0123456789")
                    prof.pinfl = prof.pinfl or get_random_string(14, "0123456789")
                    prof.gender = (StudentProfile.Gender.FEMALE if is_female
                                   else StudentProfile.Gender.MALE)
                    prof.citizenship = "O'zbekiston Respublikasi fuqarosi"
                    prof.country = "O'zbekiston"; prof.nationality = "O'zbeklar"
                    prof.region = "Namangan viloyati"
                    prof.faculty_name = fac_name
                    prof.specialty_code = direction.code
                    prof.group_name = group_name
                    prof.course = f"{course_no}-kurs"
                    prof.semester = f"{course_no*2}-semestr"
                    prof.education_type = "Bakalavr"
                    prof.education_form = "Kunduzgi"
                    prof.education_language = "O'zbek"
                    prof.academic_year = "2025-2026"
                    prof.payment_form = "To'lov-shartnoma"
                    prof.grant_type = "11 - Kontrakt"
                    if prof.gpa is None:
                        prof.gpa = Decimal(str(round(random.uniform(3.0, 5.0), 2)))
                    prof.save()

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ '{fac_name}' to'liq to'ldirildi:\n"
            f"   Kafedralar: {len(depts)} | Yo'nalishlar: {len(directions)} | "
            f"O'qituvchilar: {len(teachers)}\n"
            f"   Guruhlar: {n_groups} | Yangi talabalar: {n_students} "
            f"(har guruhda ~{per_group})\n"
            f"   Fanlar (yo'nalishlarda jami): {Course.objects.filter(curriculum__direction__faculty=faculty).count()}\n"
            f"   Dekanat (vice-dean) login: zamdekan_bb / parol123\n"
            f"   O'qituvchi login: oqituvchi_bb1 / parol123 (1..8)\n"))

    def _user(self, username, full_name):
        from accounts.models import PasswordStatus
        user, created = User.objects.get_or_create(
            username=username, defaults={"full_name": full_name})
        if created:
            user.set_password("parol123")
            user.password_status = PasswordStatus.ACTIVE
            user.save()
        return user