from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "O‘quv AI — sayt boshqaruvi"
admin.site.site_title = "O‘quv AI"
admin.site.index_title = "Boshqaruv paneli"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("hisob/", include("accounts.urls")),
    path("zamdekan/", include("portal.urls")),
    path("", include("core.urls")),
]
