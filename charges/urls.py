from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from charges.views import ChargeViewSet, health

router = DefaultRouter()
router.register("charges", ChargeViewSet, basename="charge")

urlpatterns = [
    path("", include(router.urls)),
    path("token/", obtain_auth_token, name="api-token"),
    path("health/", health, name="health"),
]
