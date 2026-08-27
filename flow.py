import os
os.environ.update(DEBUG="False",SECRET_KEY="x",ALLOWED_HOSTS="testserver")
import django; os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings"); django.setup()
os.system("DEBUG=False SECRET_KEY=x ALLOWED_HOSTS=testserver python manage.py collectstatic --no-input >/dev/null 2>&1")
from django.test import Client
from accounts.models import User
from teaching.models import TeacherAssignment
from qbank.models import TestBank
from qbank.services.docx_parser import TestQuestionDocxParser
from assessment.models import Quiz, Question, Choice, QuizAttempt
t=User.objects.get(username="oqituvchi")
ta=TeacherAssignment.objects.filter(teacher=t,status=TeacherAssignment.Status.ACTIVE).first()
bank=TestBank.objects.create(title="MathType", created_by=t)
created=TestQuestionDocxParser("/tmp/test.docx").parse_into_bank(bank)
print("Import:", len(created), "savol")
c=Client(); c.login(username="oqituvchi",password="parol123")
# test_detail sahifasida variant rasmlari chiqadimi
h=c.get(f"/zamdekan/oqituvchi/savollar-banki/test/{bank.pk}/").content.decode()
print("test_detail: savol/variant <img data:image> soni:", h.count('src="data:image'))
# test yaratish
c.post(f"/zamdekan/oqituvchi/savollar-banki/test/{bank.pk}/test-yaratish/", {"assignment":str(ta.pk),"title":"MathType quiz"})
quiz=Quiz.objects.get(title="MathType quiz")
# variant rasmli Choice bormi
ch_img=Choice.objects.filter(question__quiz=quiz).exclude(image_data="").count()
q_img=Question.objects.filter(quiz=quiz).exclude(image_data="").count()
print("Quizda: rasmli savol:", q_img, "| rasmli variant (Choice):", ch_img)
# talaba take sahifasi
st=User.objects.get(username="talaba1"); QuizAttempt.objects.filter(quiz=quiz,student=st).delete()
sc=Client(); sc.force_login(st)
th=sc.get(f"/zamdekan/talaba/testlar/{quiz.pk}/ishlash/").content.decode()
print("talaba take: <img data:image> soni:", th.count('src="data:image'))
