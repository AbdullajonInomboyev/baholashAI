from django.urls import path

from . import views, views_common, views_dept, views_quiz, views_student, views_teacher

app_name = "portal"

urlpatterns = [
    path("bildirishnomalar/", views_common.notifications, name="notifications"),
    path("bildirishnoma/<int:pk>/", views_common.notification_open, name="notification_open"),
    path("kalendar/", views_common.calendar, name="calendar"),
    path("", views.dashboard, name="dashboard"),

    path("kafedralar/", views.departments, name="departments"),
    path("kafedralar/yangi/", views.department_form, name="department_create"),
    path("kafedralar/<int:pk>/", views.department_form, name="department_edit"),
    path("kafedralar/<int:pk>/ochirish/", views.department_delete, name="department_delete"),

    path("yonalishlar/", views.directions, name="directions"),
    path("guruhlar/", views.groups, name="groups"),
    path("auditoriyalar/", views.rooms_overview, name="rooms"),
    path("auditoriyalar/bino/yangi/", views.building_form, name="building_create"),
    path("auditoriyalar/bino/<int:pk>/tahrir/", views.building_form, name="building_edit"),
    path("auditoriyalar/bino/<int:pk>/ochirish/", views.building_delete, name="building_delete"),
    path("auditoriyalar/xona/yangi/", views.room_form, name="room_create"),
    path("auditoriyalar/xona/<int:pk>/tahrir/", views.room_form, name="room_edit"),
    path("auditoriyalar/xona/<int:pk>/ochirish/", views.room_delete, name="room_delete"),
    path("guruhlar/yangi/", views.group_form, name="group_create"),
    path("guruhlar/<int:pk>/", views.group_detail, name="group_detail"),
    path("guruhlar/<int:pk>/tahrir/", views.group_form, name="group_edit"),
    path("guruhlar/<int:pk>/ochirish/", views.group_delete, name="group_delete"),
    path("guruhlar/<int:pk>/talaba-qoshish/", views.group_add_student, name="group_add_student"),
    path("guruhlar/<int:pk>/talaba/<int:enr_pk>/chiqarish/", views.group_remove_student, name="group_remove_student"),
    path("yonalishlar/yangi/", views.direction_form, name="direction_create"),
    path("yonalishlar/<int:pk>/", views.direction_form, name="direction_edit"),

    path("oquv-yili/", views.academic_years, name="years"),
    path("oquv-yili/yangi/", views.academic_year_create, name="year_create"),
    path("oquv-yili/<int:pk>/", views.year_detail, name="year_detail"),
    path("oquv-yili/<int:pk>/import/", views.year_import, name="year_import"),

    path("fanlar/", views.course_explorer, name="courses"),
    path("fanlar/royxat/", views.courses, name="courses_list"),
    path("fanlar/yangi/", views.course_form, name="course_create"),
    path("fanlar/<int:pk>/", views.course_detail, name="course_detail"),
    path("fanlar/<int:pk>/tahrirlash/", views.course_form, name="course_edit"),
    path("fanlar/<int:pk>/ochirish/", views.course_delete, name="course_delete"),
    path("fanlar/<int:pk>/biriktirish/", views.course_assign, name="course_assign"),
    path("fanlar/<int:pk>/biriktirish/<int:link_id>/olib/", views.course_unassign, name="course_unassign"),
    path("fanlar/<int:pk>/semestr/qoshish/", views.course_placement_add, name="course_placement_add"),
    path("fanlar/<int:pk>/semestr/<int:placement_id>/olib/", views.course_placement_delete, name="course_placement_delete"),
    path("fanlar/<int:pk>/mavzu/qoshish/", views.course_topic_add, name="course_topic_add"),
    path("fanlar/<int:pk>/mavzu/<int:topic_id>/olib/", views.course_topic_delete, name="course_topic_delete"),

    path("yonalishlar/<int:pk>/ochirish/", views.direction_delete, name="direction_delete"),

    path("talabalar/<int:pk>/tahrirlash/", views.student_edit, name="student_edit"),
    path("talabalar/<int:pk>/ochirish/", views.student_delete, name="student_delete"),

    path("talabalar/", views.student_list, name="students"),
    path("talabalar/import/", views.student_import, name="student_import"),
    path("talabalar/export/", views.student_export, name="student_export"),
    path("talabalar/shablon/", views.student_template, name="student_template"),

    path("hisobotlar/", views.report_center, name="reports"),
    path("hisobotlar/fakultet/", views.report_faculty, name="report_faculty"),
    path("hisobotlar/fakultet/pdf/", views.report_faculty_pdf, name="report_faculty_pdf"),
    path("hisobotlar/kafedra/<int:pk>/", views.report_department, name="report_department"),
    path("hisobotlar/izoh/", views.report_remark, name="report_remark"),

    path("parollar/", views.password_center, name="passwords"),
    path("parollar/<int:pk>/tiklash/", views.password_reset, name="password_reset"),

    # ---- Kafedra mudiri ----
    path("kafedra/", views_dept.dashboard, name="dept_dashboard"),
    path("kafedra/almashtirish/<int:pk>/", views_dept.switch_department, name="dept_switch"),
    path("kafedra/fanlar/", views_dept.courses, name="dept_courses"),
    path("kafedra/fanlar/qidirish/", views_dept.course_browser, name="dept_course_browser"),
    path("kafedra/fanlar/<int:course_pk>/biriktirish/", views_dept.course_pull, name="dept_course_pull"),
    path("kafedra/biriktiruv/<int:pk>/oqituvchilar/", views_dept.course_teachers, name="dept_course_teachers"),
    path("kafedra/biriktiruv/<int:pk>/oqituvchi/qoshish/", views_dept.teacher_assign, name="dept_teacher_assign"),
    path("kafedra/biriktiruv/<int:pk>/oqituvchi/<int:ta_pk>/olib/", views_dept.teacher_remove, name="dept_teacher_remove"),
    path("kafedra/resurslar/", views_dept.resources, name="dept_resources"),
    path("kafedra/resurslar/<int:pk>/", views_dept.resource_detail, name="dept_resource_detail"),
    path("kafedra/izohlar/", views_dept.remarks, name="dept_remarks"),
    path("kafedra/izohlar/<int:pk>/hal/", views_dept.remark_resolve, name="dept_remark_resolve"),

    # ---- O'qituvchi ----
    path("oqituvchi/", views_teacher.dashboard, name="teacher_dashboard"),
    path("oqituvchi/fanlar/", views_teacher.courses, name="teacher_courses"),
    path("oqituvchi/fanlar/<int:pk>/topshiriqlar/", views_teacher.course_assignments, name="teacher_course_assignments"),
    path("oqituvchi/fanlar/<int:pk>/topshiriq/yangi/", views_teacher.assignment_form, name="teacher_assignment_create"),
    path("oqituvchi/fanlar/<int:pk>/topshiriq/<int:assignment_pk>/", views_teacher.assignment_form, name="teacher_assignment_edit"),
    path("oqituvchi/fanlar/<int:pk>/topshiriq/<int:assignment_pk>/ochirish/", views_teacher.assignment_delete, name="teacher_assignment_delete"),
    path("oqituvchi/topshiriq/<int:assignment_pk>/ishlar/", views_teacher.submissions, name="teacher_submissions"),
    path("oqituvchi/topshiriq/<int:assignment_pk>/mezonlar/", views_teacher.assignment_criteria, name="teacher_assignment_criteria"),
    path("oqituvchi/topshiriq/<int:assignment_pk>/mezon/qoshish/", views_teacher.criterion_add, name="teacher_criterion_add"),
    path("oqituvchi/mezon/<int:pk>/ochirish/", views_teacher.criterion_delete, name="teacher_criterion_delete"),
    path("oqituvchi/ish/<int:submission_pk>/rubrika/", views_teacher.rubric_grade, name="teacher_rubric_grade"),
    path("oqituvchi/ish/<int:submission_pk>/tasdiqlash/", views_teacher.review_confirm, name="teacher_review_confirm"),
    path("oqituvchi/ish/<int:submission_pk>/ozgartirish/", views_teacher.review_override, name="teacher_review_override"),
    path("oqituvchi/jurnal/", views_teacher.gradebook, name="teacher_gradebook"),
    path("oqituvchi/resurslar/", views_teacher.resources, name="teacher_resources"),
    path("oqituvchi/resurslar/yuklash/", views_teacher.resource_upload, name="teacher_resource_upload"),

    # ---- Talaba ----
    path("talaba/", views_student.dashboard, name="student_dashboard"),
    path("talaba/topshiriqlar/", views_student.assignments, name="student_assignments"),
    path("talaba/topshiriq/<int:pk>/", views_student.assignment_detail, name="student_assignment_detail"),
    path("talaba/topshiriq/<int:pk>/topshirish/", views_student.submit, name="student_submit"),
    path("talaba/baholar/", views_student.grades, name="student_grades"),

    # ---- Test / savol banki (o'qituvchi) ----
    path("oqituvchi/testlar/", views_quiz.teacher_quizzes, name="teacher_quizzes"),
    path("oqituvchi/testlar/yangi/", views_quiz.quiz_create, name="quiz_create"),
    path("oqituvchi/testlar/<int:pk>/", views_quiz.quiz_manage, name="quiz_manage"),
    path("oqituvchi/testlar/<int:pk>/savol/", views_quiz.quiz_question_add, name="quiz_question_add"),
    path("oqituvchi/savol/<int:pk>/ochirish/", views_quiz.quiz_question_delete, name="quiz_question_delete"),
    path("oqituvchi/testlar/<int:pk>/holat/", views_quiz.quiz_toggle, name="quiz_toggle"),
    path("oqituvchi/testlar/<int:pk>/natijalar/", views_quiz.quiz_results, name="quiz_results"),
    # ---- Test (talaba) ----
    path("talaba/materiallar/", views_student.materials, name="student_materials"),
    path("talaba/testlar/", views_quiz.student_quizzes, name="student_quizzes"),
    path("talaba/testlar/<int:pk>/ishlash/", views_quiz.quiz_take, name="quiz_take"),
    path("talaba/testlar/<int:pk>/natija/", views_quiz.quiz_result, name="quiz_result"),
]
