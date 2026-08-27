import os, base64
os.environ.update(DEBUG="False",SECRET_KEY="x",ALLOWED_HOSTS="testserver")
import django; os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings"); django.setup()
from accounts.models import User
from qbank.models import TestBank
from qbank.services.docx_parser import TestQuestionDocxParser
t=User.objects.get(username="oqituvchi")
bank=TestBank.objects.create(title="s", created_by=t)
created=TestQuestionDocxParser("/tmp/test.docx").parse_into_bank(bank)
# formulali savol topib, rasmini faylga chiqaramiz
for q in created:
    if q.image_data and len(q.image_data)>1200:
        b64=q.image_data.split(",",1)[1]
        open("/tmp/q_img.png","wb").write(base64.b64decode(b64))
        print("Savol matni:", repr(q.raw_text[:50]))
        print("Variantlar:", q.correct_answer[:15], q.option1[:15], q.option2[:15])
        print("Variant rasmlari bor:", bool(q.correct_img), bool(q.option1_img), bool(q.option2_img), bool(q.option3_img))
        break
# variant rasmini ham
for q in created:
    if q.correct_img and len(q.correct_img)>1000:
        open("/tmp/opt_img.png","wb").write(base64.b64decode(q.correct_img.split(",",1)[1]))
        break
