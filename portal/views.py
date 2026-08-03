from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academics.models import (
    AcademicYear, Course, CourseSemester, Curriculum, Department, Direction,
    Semester, StudentEnrollment, StudyForm, SyllabusTopic, AcademicGroup,)
from academics.services.importer import import_curriculum
from accounts.models import PasswordStatus, Role, UserRole
from core.audit import log_action
from core.models import ReportExport, ReviewRemark
from teaching.models import DepartmentCourse

from .access import role_required, vice_dean_faculty
from .forms import (
    AcademicYearForm, AssignCourseForm, CourseForm, CoursePlacementForm,
    AcademicGroupForm, DepartmentForm, DirectionForm, ImportForm, ReportRemarkForm,
    StudentImportForm, StudentProfileForm, SyllabusTopicForm,
)
from .services import reports, students

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _paginate(request, qs, per_page=25):
    page = Paginator(qs, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    qstr = params.urlencode()
    return page, (qstr + "&" if qstr else "")


def _base(request):
    faculty = vice_dean_faculty(request.user)
    return faculty, {"panel_title": "Zam dekan paneli",
                     "panel_scope": faculty.name if faculty else "Fakultet biriktirilmagan"}


def _xlsx_response(data, filename):
    response = HttpResponse(data, content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@role_required(Role.VICE_DEAN)
def dashboard(request):
    faculty, ctx = _base(request)
    if not faculty:
        return render(request, "portal/vice_dean/no_faculty.html", ctx)
    directions = Direction.objects.filter(faculty=faculty)
    ctx.update({
        "active": "dashboard",
        "n_departments": Department.objects.filter(faculty=faculty).count(),
        "n_directions": directions.count(),
        "n_years": AcademicYear.objects.filter(faculty=faculty).count(),
        "n_courses": Course.objects.filter(curriculum__direction__in=directions).count(),
        "n_students": StudentEnrollment.objects.filter(academic_year__faculty=faculty).count(),
        "open_remarks": ReviewRemark.objects.filter(
            department__faculty=faculty, status=ReviewRemark.Status.OPEN).count(),
        "recent_years": AcademicYear.objects.filter(faculty=faculty)[:5],
    })
    return render(request, "portal/vice_dean/dashboard.html", ctx)


# ---- Kafedralar ----
@role_required(Role.VICE_DEAN)
def departments(request):
    faculty, ctx = _base(request)
    ctx.update({"active": "departments",
                "departments": Department.objects.filter(faculty=faculty)
                .select_related("head").annotate(n=Count("course_links"))})
    return render(request, "portal/vice_dean/departments.html", ctx)


@role_required(Role.VICE_DEAN)
def department_form(request, pk=None):
    faculty, ctx = _base(request)
    instance = get_object_or_404(Department, pk=pk, faculty=faculty) if pk else None
    form = DepartmentForm(request.POST or None, instance=instance, faculty=faculty)
    if instance:
        form.fields["head"].queryset = _faculty_staff(faculty)
    else:
        form.fields["head"].queryset = _faculty_staff(faculty)
    if request.method == "POST" and form.is_valid():
        dept = form.save(commit=False)
        dept.faculty = faculty
        dept.save()
        if dept.head:
            UserRole.objects.get_or_create(user=dept.head, role=Role.DEPT_HEAD, department=dept)
        messages.success(request, "Kafedra saqlandi.")
        return redirect("portal:departments")
    ctx.update({"active": "departments", "form": form, "instance": instance})
    return render(request, "portal/vice_dean/department_form.html", ctx)


@role_required(Role.VICE_DEAN)
def department_delete(request, pk):
    faculty, _ = _base(request)
    dept = get_object_or_404(Department, pk=pk, faculty=faculty)
    if request.method == "POST":
        dept.delete()
        messages.success(request, "Kafedra o‘chirildi.")
    return redirect("portal:departments")


# ---- Yo'nalishlar ----
@role_required(Role.VICE_DEAN)
def directions(request):
    faculty, ctx = _base(request)
    ctx.update({"active": "directions",
                "directions": Direction.objects.filter(faculty=faculty).select_related("department")})
    return render(request, "portal/vice_dean/directions.html", ctx)


@role_required(Role.VICE_DEAN)
def direction_form(request, pk=None):
    faculty, ctx = _base(request)
    instance = get_object_or_404(Direction, pk=pk, faculty=faculty) if pk else None
    form = DirectionForm(request.POST or None, instance=instance, faculty=faculty)
    if request.method == "POST" and form.is_valid():
        direction = form.save(commit=False)
        direction.faculty = faculty
        direction.save()
        messages.success(request, "Yo‘nalish saqlandi.")
        return redirect("portal:directions")
    ctx.update({"active": "directions", "form": form, "instance": instance})
    return render(request, "portal/vice_dean/direction_form.html", ctx)


# ---- O'quv yili + import ----
@role_required(Role.VICE_DEAN)
def academic_years(request):
    faculty, ctx = _base(request)
    ctx.update({"active": "years", "form": AcademicYearForm(),
                "years": AcademicYear.objects.filter(faculty=faculty)
                .annotate(n=Count("semesters", distinct=True))})
    return render(request, "portal/vice_dean/years.html", ctx)


@role_required(Role.VICE_DEAN)
def academic_year_create(request):
    faculty, _ = _base(request)
    form = AcademicYearForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        year = form.save(commit=False)
        year.faculty = faculty
        year.save()
        messages.success(request, "O‘quv yili ochildi.")
    return redirect("portal:years")


@role_required(Role.VICE_DEAN)
def year_detail(request, pk):
    faculty, ctx = _base(request)
    year = get_object_or_404(AcademicYear, pk=pk, faculty=faculty)
    study_form = request.GET.get("form", StudyForm.FULL_TIME)
    semesters = []
    for sem in year.semesters.all():
        placements = (CourseSemester.objects
                      .filter(semester=sem, course__curriculum__study_form=study_form,
                              course__curriculum__academic_year=year,
                              course__curriculum__direction__faculty=faculty)
                      .select_related("course").order_by("course__code"))
        if placements:
            semesters.append((sem, placements))
    ctx.update({"active": "years", "year": year, "semesters": semesters,
                "study_form": study_form, "study_forms": StudyForm.choices,
                "import_form": ImportForm(faculty=faculty),
                "imports": year.imports.all()[:6]})
    return render(request, "portal/vice_dean/year_detail.html", ctx)


@role_required(Role.VICE_DEAN)
def year_import(request, pk):
    faculty, _ = _base(request)
    year = get_object_or_404(AcademicYear, pk=pk, faculty=faculty)
    form = ImportForm(request.POST, request.FILES, faculty=faculty)
    if form.is_valid():
        try:
            result = import_curriculum(
                year, form.cleaned_data["file"],
                uploaded_by=request.user, forms=form.cleaned_data["forms_to_import"],
                direction=form.cleaned_data.get("direction"),
            )
            log_action(request.user, "import", "AcademicYear", year.pk,
                       new={"courses": result["courses"], "forms": result["forms"]})
            messages.success(
                request,
                f"Import yakunlandi: {result['direction'].code} — {result['courses']} ta fan yozuvi. "
                "Ogohlantirishlarni import jurnalidan ko‘ring."
            )
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Import xatosi: {exc}")
    else:
        messages.error(request, "Fayl yoki ta‘lim shakli tanlanmadi.")
    return redirect("portal:year_detail", pk=year.pk)


# ---- Fanlar ----
@role_required(Role.VICE_DEAN)
def courses(request):
    faculty, ctx = _base(request)
    qs = (Course.objects.filter(curriculum__direction__faculty=faculty)
          .select_related("curriculum__direction").prefetch_related("department_links__department"))
    direction_id = request.GET.get("direction")
    study_form = request.GET.get("form")
    query = request.GET.get("q", "").strip()
    if direction_id:
        qs = qs.filter(curriculum__direction_id=direction_id)
    if study_form:
        qs = qs.filter(curriculum__study_form=study_form)
    if query:
        qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query))
    page, qstring = _paginate(request, qs, 30)
    ctx.update({"active": "courses", "courses": page, "page_obj": page, "qstring": qstring,
                "directions": Direction.objects.filter(faculty=faculty),
                "study_forms": StudyForm.choices,
                "f_direction": direction_id, "f_form": study_form, "q": query})
    return render(request, "portal/vice_dean/courses.html", ctx)


@role_required(Role.VICE_DEAN)
def course_form(request, pk=None):
    faculty, ctx = _base(request)
    instance = get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty) if pk else None
    form = CourseForm(request.POST or None, instance=instance, faculty=faculty)
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.credit = None  # save() qayta hisoblaydi
        course.save()
        messages.success(request, "Fan saqlandi.")
        return redirect("portal:courses")
    ctx.update({"active": "courses", "form": form, "instance": instance})
    return render(request, "portal/vice_dean/course_form.html", ctx)


@role_required(Role.VICE_DEAN)
def course_assign(request, pk):
    faculty, ctx = _base(request)
    course = get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty)
    form = AssignCourseForm(request.POST or None, faculty=faculty)
    if request.method == "POST" and form.is_valid():
        DepartmentCourse.objects.get_or_create(
            department=form.cleaned_data["department"], course=course,
            defaults={"assigned_by": request.user},
        )
        messages.success(request, "Fan kafedraga biriktirildi.")
        return redirect("portal:courses")
    ctx.update({"active": "courses", "form": form, "course": course,
                "current": course.department_links.select_related("department")})
    return render(request, "portal/vice_dean/course_assign.html", ctx)


# ---- Talabalar ----
@role_required(Role.VICE_DEAN)
def student_list(request):
    faculty, ctx = _base(request)
    years = AcademicYear.objects.filter(faculty=faculty)
    year_id = request.GET.get("year") or (years.first().pk if years else None)
    enrollments = (StudentEnrollment.objects
                   .filter(academic_year__faculty=faculty)
                   .select_related("student", "direction", "academic_year"))
    if year_id:
        enrollments = enrollments.filter(academic_year_id=year_id)
    page, qstring = _paginate(request, enrollments.order_by("group_name", "student__full_name"), 30)
    ctx.update({"active": "students", "years": years, "year_id": int(year_id) if year_id else None,
                "enrollments": page, "page_obj": page, "qstring": qstring,
                "import_form": StudentImportForm()})
    return render(request, "portal/vice_dean/students.html", ctx)


@role_required(Role.VICE_DEAN)
def student_import(request):
    faculty, _ = _base(request)
    year = get_object_or_404(AcademicYear, pk=request.POST.get("year"), faculty=faculty)
    form = StudentImportForm(request.POST, request.FILES)
    if form.is_valid():
        result = students.import_students(year, form.cleaned_data["file"])
        log_action(request.user, "import", "StudentEnrollment", year.pk, new=result)
        msg = f"Import: {result['created']} yangi, {result['updated']} yangilangan."
        if result["errors"]:
            msg += f" {len(result['errors'])} qatorda xato."
            messages.warning(request, msg + " " + " | ".join(result["errors"][:5]))
        else:
            messages.success(request, msg)
    else:
        messages.error(request, "Fayl tanlanmadi.")
    return redirect(f"/zamdekan/talabalar/?year={year.pk}")


@role_required(Role.VICE_DEAN)
def student_export(request):
    faculty, _ = _base(request)
    year = get_object_or_404(AcademicYear, pk=request.GET.get("year"), faculty=faculty)
    data = students.export_students(year)
    return _xlsx_response(data, f"talabalar_{year.title}.xlsx")


@role_required(Role.VICE_DEAN)
def student_template(request):
    return _xlsx_response(students.build_template(), "talabalar_shablon.xlsx")


# ---- Hisobotlar ----
@role_required(Role.VICE_DEAN)
def report_center(request):
    faculty, ctx = _base(request)
    ctx.update({"active": "reports",
                "departments": Department.objects.filter(faculty=faculty),
                "remark_form": ReportRemarkForm(faculty=faculty),
                "history": ReportExport.objects.filter(faculty=faculty)[:10],
                "sent_remarks": ReviewRemark.objects.filter(department__faculty=faculty)
                .select_related("target", "department")[:10]})
    return render(request, "portal/vice_dean/reports.html", ctx)


@role_required(Role.VICE_DEAN)
def report_faculty(request):
    faculty, _ = _base(request)
    data = reports.faculty_report(faculty)
    ReportExport.objects.create(generated_by=request.user, scope=ReportExport.Scope.FACULTY,
                                faculty=faculty)
    return _xlsx_response(data, f"fakultet_hisobot_{faculty.pk}.xlsx")


@role_required(Role.VICE_DEAN)
def report_faculty_pdf(request):
    faculty, _ = _base(request)
    data = reports.faculty_report_pdf(faculty)
    ReportExport.objects.create(generated_by=request.user, scope=ReportExport.Scope.FACULTY,
                                faculty=faculty)
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="fakultet_hisobot_{faculty.pk}.pdf"'
    return resp


@role_required(Role.VICE_DEAN)
def report_department(request, pk):
    faculty, _ = _base(request)
    dept = get_object_or_404(Department, pk=pk, faculty=faculty)
    data = reports.department_report(dept)
    ReportExport.objects.create(generated_by=request.user, scope=ReportExport.Scope.DEPARTMENT,
                                faculty=faculty, department=dept)
    return _xlsx_response(data, f"kafedra_hisobot_{dept.pk}.xlsx")


@role_required(Role.VICE_DEAN)
def report_remark(request):
    faculty, _ = _base(request)
    form = ReportRemarkForm(request.POST or None, faculty=faculty)
    if request.method == "POST" and form.is_valid():
        dept = form.cleaned_data["department"]
        if not dept.head:
            messages.error(request, "Bu kafedrada mudir tayinlanmagan — izoh yuborib bo‘lmadi.")
        else:
            remark = ReviewRemark.objects.create(
                author=request.user, target=dept.head, department=dept,
                message=form.cleaned_data["message"],
            )
            log_action(request.user, "remark", "ReviewRemark", remark.pk)
            messages.success(request, f"Izoh {dept.head} ga yuborildi.")
    return redirect("portal:reports")


# ---- Parol tiklash ----
@role_required(Role.VICE_DEAN)
def password_center(request):
    faculty, ctx = _base(request)
    lower = (UserRole.objects
             .filter(Q(faculty=faculty) | Q(department__faculty=faculty))
             .exclude(role__in=[Role.ADMIN, Role.VICE_DEAN])
             .select_related("user").order_by("user__full_name"))
    seen, people = set(), []
    for link in lower:
        if link.user_id not in seen:
            seen.add(link.user_id)
            people.append(link.user)
    ctx.update({"active": "passwords", "people": people})
    return render(request, "portal/vice_dean/passwords.html", ctx)


@role_required(Role.VICE_DEAN)
def password_reset(request, pk):
    from django.contrib.auth import get_user_model
    from django.utils.crypto import get_random_string
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        temp = get_random_string(8)
        user.set_password(temp)
        user.password_status = PasswordStatus.TEMPORARY
        user.save()
        log_action(request.user, "password_reset", "User", user.pk)
        messages.success(request, f"{user} uchun vaqtinchalik parol: {temp} "
                                  "(foydalanuvchi birinchi kirishda o‘zgartiradi).")
    return redirect("portal:passwords")


def _faculty_staff(faculty):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(
        Q(roles__faculty=faculty) | Q(roles__department__faculty=faculty)
    ).distinct()


def _active_year(faculty):
    return (AcademicYear.objects.filter(faculty=faculty, is_active=True).order_by("-title").first()
            or AcademicYear.objects.filter(faculty=faculty).order_by("-title").first())


# ---- Fan (batafsil) ----
@role_required(Role.VICE_DEAN)
def course_detail(request, pk):
    faculty, ctx = _base(request)
    course = get_object_or_404(
        Course.objects.select_related("curriculum__direction"), pk=pk,
        curriculum__direction__faculty=faculty)
    placements = course.placements.select_related("semester").order_by("semester__number")
    dept_links = course.department_links.select_related("department").all()
    from teaching.models import TeacherAssignment
    teachers = (TeacherAssignment.objects
                .filter(department_course__in=dept_links, status=TeacherAssignment.Status.ACTIVE)
                .select_related("teacher", "department_course__department"))
    ctx.update({
        "active": "courses", "course": course, "placements": placements,
        "dept_links": dept_links, "teachers": teachers,
        "topics": course.topics.all(),
        "placement_form": CoursePlacementForm(),
        "topic_form": SyllabusTopicForm(),
        "assign_form": AssignCourseForm(faculty=faculty),
    })
    return render(request, "portal/vice_dean/course_detail.html", ctx)


@role_required(Role.VICE_DEAN)
def course_delete(request, pk):
    faculty, _ = _base(request)
    course = get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty)
    if request.method == "POST":
        course.delete()
        messages.success(request, "Fan o‘chirildi.")
        return redirect("portal:courses")
    return redirect("portal:course_detail", pk=pk)


@role_required(Role.VICE_DEAN)
def course_placement_add(request, pk):
    faculty, _ = _base(request)
    course = get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty)
    form = CoursePlacementForm(request.POST)
    year = course.curriculum.academic_year
    if not year:
        messages.error(request, "Avval o‘quv yili oching.")
    elif form.is_valid():
        semester, _ = Semester.objects.get_or_create(
            academic_year=year, number=form.cleaned_data["semester_number"])
        CourseSemester.objects.update_or_create(
            course=course, semester=semester,
            defaults={"credits": form.cleaned_data["credits"],
                      "weekly_hours": form.cleaned_data["weekly_hours"]})
        messages.success(request, "Semestr taqsimoti saqlandi.")
    else:
        messages.error(request, "Ma‘lumot noto‘g‘ri.")
    return redirect("portal:course_detail", pk=pk)


@role_required(Role.VICE_DEAN)
def course_placement_delete(request, pk, placement_id):
    faculty, _ = _base(request)
    get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty)
    CourseSemester.objects.filter(pk=placement_id, course_id=pk).delete()
    messages.success(request, "Semestrdan olib tashlandi.")
    return redirect("portal:course_detail", pk=pk)


@role_required(Role.VICE_DEAN)
def course_topic_add(request, pk):
    faculty, _ = _base(request)
    course = get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty)
    form = SyllabusTopicForm(request.POST)
    if form.is_valid():
        SyllabusTopic.objects.update_or_create(
            course=course, order=form.cleaned_data["order"],
            defaults={"title": form.cleaned_data["title"]})
        messages.success(request, "Mavzu saqlandi.")
    else:
        messages.error(request, "Mavzu ma‘lumoti noto‘g‘ri.")
    return redirect("portal:course_detail", pk=pk)


@role_required(Role.VICE_DEAN)
def course_topic_delete(request, pk, topic_id):
    faculty, _ = _base(request)
    get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty)
    SyllabusTopic.objects.filter(pk=topic_id, course_id=pk).delete()
    messages.success(request, "Mavzu o‘chirildi.")
    return redirect("portal:course_detail", pk=pk)


@role_required(Role.VICE_DEAN)
def course_unassign(request, pk, link_id):
    faculty, _ = _base(request)
    get_object_or_404(Course, pk=pk, curriculum__direction__faculty=faculty)
    DepartmentCourse.objects.filter(pk=link_id, course_id=pk).delete()
    messages.success(request, "Kafedradan olib tashlandi.")
    return redirect("portal:course_detail", pk=pk)


@role_required(Role.VICE_DEAN)
def direction_delete(request, pk):
    faculty, _ = _base(request)
    direction = get_object_or_404(Direction, pk=pk, faculty=faculty)
    if request.method == "POST":
        if direction.curricula.exists():
            messages.error(request, "Bu yo‘nalishda fanlar bor — avval ularni o‘chiring.")
        else:
            direction.delete()
            messages.success(request, "Yo‘nalish o‘chirildi.")
    return redirect("portal:directions")


# ---- Talaba (batafsil / tahrirlash) ----
@role_required(Role.VICE_DEAN)
def student_edit(request, pk):
    faculty, ctx = _base(request)
    enrollment = get_object_or_404(
        StudentEnrollment.objects.select_related("student", "direction", "academic_year"),
        pk=pk, academic_year__faculty=faculty)
    student = enrollment.student
    initial = {
        "full_name": student.full_name, "email": student.email, "phone": student.phone,
        "group_name": enrollment.group_name, "status": enrollment.status,
        "direction": enrollment.direction_id, "study_form": enrollment.study_form,
    }
    form = StudentProfileForm(request.POST or None, initial=initial, faculty=faculty)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        student.full_name = d["full_name"]; student.email = d["email"]; student.phone = d["phone"]
        student.save(update_fields=["full_name", "email", "phone"])
        enrollment.group_name = d["group_name"]; enrollment.status = d["status"]
        enrollment.direction = d["direction"]; enrollment.study_form = d["study_form"]
        enrollment.save()
        messages.success(request, "Talaba ma‘lumoti saqlandi.")
        return redirect(f"/zamdekan/talabalar/?year={enrollment.academic_year_id}")
    ctx.update({"active": "students", "form": form, "enrollment": enrollment, "student": student})
    return render(request, "portal/vice_dean/student_edit.html", ctx)


@role_required(Role.VICE_DEAN)
def student_delete(request, pk):
    faculty, _ = _base(request)
    enrollment = get_object_or_404(StudentEnrollment, pk=pk, academic_year__faculty=faculty)
    year_id = enrollment.academic_year_id
    if request.method == "POST":
        enrollment.delete()
        messages.success(request, "Talaba biriktiruvi olib tashlandi.")
    return redirect(f"/zamdekan/talabalar/?year={year_id}")


@role_required(Role.VICE_DEAN)
def course_explorer(request):
    """Ikki ustunli, daraxtli, master-detail: O‘quv yili → Yo‘nalish → Semestr → Fan."""
    from teaching.models import TeacherAssignment
    faculty, ctx = _base(request)
    study_form = request.GET.get("form", StudyForm.FULL_TIME)
    years = AcademicYear.objects.filter(faculty=faculty).order_by("-title")

    sel_year = request.GET.get("year")
    sel_dir = request.GET.get("dir")
    sel_sem = request.GET.get("sem")
    sel_course = request.GET.get("course")

    # daraxt: yil -> kafedra -> yo'nalish -> semestr
    tree = []
    for y in years:
        curricula = (Curriculum.objects
                     .filter(academic_year=y, study_form=study_form, direction__faculty=faculty)
                     .select_related("direction__department"))
        dept_map = {}  # dept -> [dir_node...]
        for cur in curricula:
            base = Course.objects.filter(curriculum=cur)
            sems = []
            for n in range(1, 9):
                cnt = base.filter(placements__semester__number=n).distinct().count()
                if cnt:
                    sems.append({"n": n, "count": cnt})
            node = {"dir": cur.direction, "total": base.count(), "sems": sems,
                    "elective": base.filter(is_elective=True).count()}
            dept = cur.direction.department
            dept_map.setdefault(dept, []).append(node)
        depts = []
        for dept, dnodes in dept_map.items():
            depts.append({"dept": dept, "dirs": dnodes,
                          "total": sum(x["total"] for x in dnodes)})
        depts.sort(key=lambda d: (d["dept"].name if d["dept"] else "яя"))
        if depts:
            tree.append({"year": y, "depts": depts})

    detail = None
    course_list = None
    heading = None

    if sel_course:
        course = get_object_or_404(
            Course.objects.select_related("curriculum__direction", "curriculum__academic_year"),
            pk=sel_course, curriculum__direction__faculty=faculty)
        dept_links = course.department_links.select_related("department").all()
        teachers = (TeacherAssignment.objects
                    .filter(department_course__in=dept_links, status=TeacherAssignment.Status.ACTIVE)
                    .select_related("teacher"))
        detail = {
            "course": course,
            "placements": course.placements.select_related("semester").order_by("semester__number"),
            "dept_links": dept_links, "teachers": teachers,
            "topics": course.topics.all(),
        }
        sel_year = str(course.curriculum.academic_year_id)
        sel_dir = str(course.curriculum.direction_id)
    elif sel_year and sel_dir:
        qs = Course.objects.filter(
            curriculum__academic_year_id=sel_year, curriculum__direction_id=sel_dir,
            curriculum__study_form=study_form)
        if sel_sem:
            qs = qs.filter(placements__semester__number=sel_sem).distinct()
        course_list = qs.order_by("code")
        yobj = years.filter(pk=sel_year).first()
        dobj = Direction.objects.filter(pk=sel_dir).first()
        parts = [p for p in [yobj.title if yobj else None, dobj.code if dobj else None,
                             f"{sel_sem}-semestr" if sel_sem else None] if p]
        heading = " · ".join(parts)

    ctx.update({"active": "courses", "tree": tree, "study_form": study_form,
                "study_forms": StudyForm.choices, "sel_year": sel_year, "sel_dir": sel_dir,
                "sel_sem": sel_sem, "sel_course": sel_course, "detail": detail,
                "course_list": course_list, "heading": heading})
    return render(request, "portal/vice_dean/course_explorer.html", ctx)


# ==================== Akademik guruhlar ====================

@role_required(Role.VICE_DEAN)
def groups(request):
    faculty, ctx = _base(request)
    qs = (AcademicGroup.objects.filter(direction__faculty=faculty)
          .select_related("direction", "curator", "academic_year"))
    f_course = request.GET.get("course")
    if f_course:
        qs = qs.filter(course=f_course)
    ctx.update({"active": "groups", "groups": qs, "f_course": f_course,
                "courses": [1, 2, 3, 4, 5, 6]})
    return render(request, "portal/vice_dean/groups.html", ctx)


@role_required(Role.VICE_DEAN)
def group_form(request, pk=None):
    faculty, ctx = _base(request)
    instance = get_object_or_404(AcademicGroup, pk=pk, direction__faculty=faculty) if pk else None
    form = AcademicGroupForm(request.POST or None, instance=instance, faculty=faculty)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guruh saqlandi.")
        return redirect("portal:groups")
    ctx.update({"active": "groups", "form": form, "instance": instance})
    return render(request, "portal/vice_dean/group_form.html", ctx)


@role_required(Role.VICE_DEAN)
def group_delete(request, pk):
    faculty, _ = _base(request)
    group = get_object_or_404(AcademicGroup, pk=pk, direction__faculty=faculty)
    group.delete()
    messages.success(request, "Guruh o‘chirildi.")
    return redirect("portal:groups")


@role_required(Role.VICE_DEAN)
def group_detail(request, pk):
    faculty, ctx = _base(request)
    group = get_object_or_404(
        AcademicGroup.objects.select_related("direction", "curator"),
        pk=pk, direction__faculty=faculty)
    members = group.members.select_related("student", "academic_year").order_by("student__full_name")
    available = (StudentEnrollment.objects
                 .filter(direction=group.direction, study_form=group.study_form, group__isnull=True)
                 .select_related("student")[:100])
    ctx.update({"active": "groups", "group": group, "members": members, "available": available})
    return render(request, "portal/vice_dean/group_detail.html", ctx)


@role_required(Role.VICE_DEAN)
def group_add_student(request, pk):
    faculty, _ = _base(request)
    group = get_object_or_404(AcademicGroup, pk=pk, direction__faculty=faculty)
    enr = get_object_or_404(StudentEnrollment, pk=request.POST.get("enrollment"),
                            direction=group.direction)
    enr.group = group
    enr.group_name = group.name
    enr.save(update_fields=["group", "group_name"])
    messages.success(request, "Talaba guruhga qo‘shildi.")
    return redirect("portal:group_detail", pk=pk)


@role_required(Role.VICE_DEAN)
def group_remove_student(request, pk, enr_pk):
    faculty, _ = _base(request)
    group = get_object_or_404(AcademicGroup, pk=pk, direction__faculty=faculty)
    enr = get_object_or_404(StudentEnrollment, pk=enr_pk, group=group)
    enr.group = None
    enr.save(update_fields=["group"])
    messages.success(request, "Talaba guruhdan chiqarildi.")
    return redirect("portal:group_detail", pk=pk)


# ==================== Auditoriyalar (binolar/xonalar) ====================

from portal.forms import BuildingForm, RoomForm  # noqa: E402
from schedule.models import Building, Room  # noqa: E402


@role_required(Role.VICE_DEAN)
def rooms_overview(request):
    faculty, ctx = _base(request)
    buildings = Building.objects.prefetch_related("rooms").all()
    ctx.update({"active": "rooms", "buildings": buildings,
                "building_form": BuildingForm(), "room_form": RoomForm()})
    return render(request, "portal/vice_dean/rooms.html", ctx)


@role_required(Role.VICE_DEAN)
def building_form(request, pk=None):
    faculty, ctx = _base(request)
    instance = get_object_or_404(Building, pk=pk) if pk else None
    form = BuildingForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bino saqlandi.")
        return redirect("portal:rooms")
    ctx.update({"active": "rooms", "form": form, "instance": instance, "kind_label": "Bino"})
    return render(request, "portal/vice_dean/room_form.html", ctx)


@role_required(Role.VICE_DEAN)
def building_delete(request, pk):
    get_object_or_404(Building, pk=pk).delete()
    messages.success(request, "Bino o‘chirildi.")
    return redirect("portal:rooms")


@role_required(Role.VICE_DEAN)
def room_form(request, pk=None):
    faculty, ctx = _base(request)
    instance = get_object_or_404(Room, pk=pk) if pk else None
    form = RoomForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Auditoriya saqlandi.")
        return redirect("portal:rooms")
    ctx.update({"active": "rooms", "form": form, "instance": instance, "kind_label": "Auditoriya"})
    return render(request, "portal/vice_dean/room_form.html", ctx)


@role_required(Role.VICE_DEAN)
def room_delete(request, pk):
    get_object_or_404(Room, pk=pk).delete()
    messages.success(request, "Auditoriya o‘chirildi.")
    return redirect("portal:rooms")


# ==================== O'qituvchilar (zam dekan ko'rinishi) ====================

@role_required(Role.VICE_DEAN)
def teachers_list(request):
    from teaching.models import TeacherAssignment
    faculty, ctx = _base(request)
    assignments = (TeacherAssignment.objects
                   .filter(status=TeacherAssignment.Status.ACTIVE,
                           department_course__department__faculty=faculty)
                   .select_related("teacher", "department_course__course",
                                   "department_course__department"))
    rows = {}
    for a in assignments:
        t = a.teacher
        row = rows.setdefault(t.id, {"teacher": t, "depts": set(), "courses": 0, "hours": 0})
        row["depts"].add(a.department_course.department.name)
        row["courses"] += 1
        row["hours"] += a.department_course.course.total_hours or 0
    teachers = sorted(rows.values(), key=lambda r: (r["teacher"].full_name or r["teacher"].username))
    ctx.update({"active": "teachers", "teachers": teachers})
    return render(request, "portal/vice_dean/teachers.html", ctx)


@role_required(Role.VICE_DEAN)
def teacher_profile(request, pk):
    from academics.models import AcademicGroup
    from teaching.models import TeacherAssignment
    faculty, ctx = _base(request)
    teacher = get_object_or_404(get_user_model(), pk=pk)
    assignments = (TeacherAssignment.objects
                   .filter(teacher=teacher, status=TeacherAssignment.Status.ACTIVE,
                           department_course__department__faculty=faculty)
                   .select_related("department_course__course", "department_course__department"))
    total_hours = sum(a.department_course.course.total_hours or 0 for a in assignments)
    groups = AcademicGroup.objects.filter(curator=teacher, direction__faculty=faculty)
    ctx.update({"active": "teachers", "teacher_obj": teacher, "assignments": assignments,
                "total_hours": total_hours, "curated_groups": groups})
    return render(request, "portal/vice_dean/teacher_profile.html", ctx)
