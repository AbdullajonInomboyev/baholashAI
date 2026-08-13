import os
os.environ["DEBUG"]="False"; os.environ["SECRET_KEY"]="x"; os.environ["ALLOWED_HOSTS"]="testserver"
import django; os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings"); django.setup()
os.system("DEBUG=False SECRET_KEY=x ALLOWED_HOSTS=testserver python manage.py collectstatic --no-input >/dev/null 2>&1")
from django.test import Client
# CSS da media qoidalari
css=open("static/css/app.css").read()
print("CSS: 1024 drawer:", "@media (max-width: 1024px)" in css, "| 640 mobil:", "@media (max-width: 640px)" in css, "| 380:", "@media (max-width: 380px)" in css)
print("CSS: table-scroll:", ".table-scroll" in css, "| nav-overlay:", "#nav-overlay" in css, "| chart-row stack:", ".chart-row,.two-col{grid-template-columns:1fr" in css)
# base_panel: overlay + JS
c=Client(raise_request_exception=True); c.login(username="talaba1", password="parol123")
b=c.get("/zamdekan/talaba/").content.decode()
print("HTML: overlay div:", 'id="nav-overlay"' in b, "| viewport meta:", 'width=device-width' in b, "| table-wrap JS:", "table-scroll" in b, "| drawer close JS:", "nav-open" in b)
# barcha rollar 200 (moslashuv hech narsani buzmaganini tekshiramiz)
def ck(uu,pw,urls):
    cc=Client(raise_request_exception=True); cc.login(username=uu,password=pw)
    bad=[u for u in urls if cc.get(u).status_code!=200]
    print("  ok" if not bad else "  XATO", uu, bad if bad else f"({len(urls)})")
ck("talaba1","parol123",["/zamdekan/talaba/","/zamdekan/talaba/fanlarim/","/zamdekan/talaba/dars-jadvali/","/zamdekan/talaba/testlar/","/zamdekan/talaba/imtihonlar/","/zamdekan/talaba/ozlashtirish/","/zamdekan/talaba/profil/"])
ck("oqituvchi","parol123",["/zamdekan/oqituvchi/","/zamdekan/oqituvchi/fanlarim/","/zamdekan/oqituvchi/dars-jadvali/","/zamdekan/oqituvchi/savollar-banki/","/zamdekan/oqituvchi/resurslar/","/zamdekan/oqituvchi/elonlar/"])
ck("mudir","parol123",["/zamdekan/kafedra/","/zamdekan/kafedra/dars-jadvali/","/zamdekan/kafedra/elektron-resurslar/","/zamdekan/kafedra/elonlar/"])
ck("zamdekan","parol123",["/zamdekan/","/zamdekan/dars-jadvali/","/zamdekan/talabalar/","/zamdekan/guruhlar/","/zamdekan/elonlar-joylash/"])
