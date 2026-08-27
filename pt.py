import os, time
os.environ.update(DEBUG="False",SECRET_KEY="x",ALLOWED_HOSTS="testserver")
import django; os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings"); django.setup()
from qbank.services.formula_image import available
print("Konvertor mavjud (libwmf/soffice):", available())
from accounts.models import User
from qbank.models import TestBank, TestQuestion
t=User.objects.get(username="oqituvchi")
bank=TestBank.objects.create(title="MathType sinov", created_by=t)
from qbank.services.docx_parser import TestQuestionDocxParser
start=time.time()
created=TestQuestionDocxParser("/tmp/test.docx").parse_into_bank(bank)
print(f"Import: {len(created)} savol | vaqt: {time.time()-start:.1f}s")
# statistika
qimg=sum(1 for q in created if q.image_data)
optimg=sum(1 for q in created if q.correct_img or q.option1_img or q.option2_img or q.option3_img)
print(f"Savol rasmli: {qimg} | variant rasmli: {optimg}")
# namuna: formulali savol
for q in created:
    if q.image_data and q.image_data.startswith("data:image"):
        print("Namuna savol image_data boshi:", q.image_data[:40], "| uzunlik:", len(q.image_data))
        break
for q in created:
    if q.correct_img:
        print("Namuna variant rasm boshi:", q.correct_img[:40])
        break
