import pytest
from rest_framework.test import APIRequestFactory

from charges.permissions import IsChargeOwner

pytestmark = pytest.mark.django_db


def _request_from(user):
    request = APIRequestFactory().get("/")
    request.user = user
    return request


def test_owner_has_object_permission(make_charge, owner):
    assert IsChargeOwner().has_object_permission(_request_from(owner), None, make_charge())


def test_other_user_has_no_object_permission(make_charge, other_owner):
    assert not IsChargeOwner().has_object_permission(
        _request_from(other_owner), None, make_charge()
    )
