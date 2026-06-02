"""Auth flow tests — registration, verification, cookie login, refresh rotation, RBAC.

Body assertions read ``resp.json()`` (the rendered envelope) rather than
``resp.data`` (the raw, pre-render serializer output), because the
``{data, meta, errors}`` envelope is applied by the renderer at render time.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.tokens import make_email_verify_token

User = get_user_model()

PASSWORD = "StrongPass123!"
LOGIN_URL = "/api/v1/auth/login/"
REGISTER_URL = "/api/v1/auth/register/"
ME_URL = "/api/v1/auth/me/"
REFRESH_URL = "/api/v1/auth/refresh/"
VERIFY_URL = "/api/v1/auth/verify-email/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def verified_user(db):
    user = User.objects.create_user(email="rider@example.com", password=PASSWORD, full_name="Rider")
    user.is_verified = True
    user.save(update_fields=["is_verified"])
    return user


@pytest.mark.django_db
def test_register_creates_unverified_passenger(client):
    resp = client.post(
        REGISTER_URL,
        {"email": "New@Example.com", "password": PASSWORD, "full_name": "New"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["email"] == "new@example.com"  # normalized to lowercase
    user = User.objects.get(email="new@example.com")
    assert user.is_verified is False
    assert user.role == User.Roles.PASSENGER


@pytest.mark.django_db
def test_register_rejects_weak_password(client):
    resp = client.post(REGISTER_URL, {"email": "a@b.com", "password": "123"}, format="json")
    assert resp.status_code == 400
    body = resp.json()
    assert body["data"] is None
    assert any(e["field"] == "password" for e in body["errors"])


@pytest.mark.django_db
def test_login_sets_httponly_strict_cookies(client, verified_user):
    resp = client.post(
        LOGIN_URL, {"email": "rider@example.com", "password": PASSWORD}, format="json"
    )
    assert resp.status_code == 200
    for name in ("st_access", "st_refresh"):
        assert name in resp.cookies
        assert resp.cookies[name]["httponly"] is True
        assert resp.cookies[name]["samesite"] == "Strict"
    # No token is ever placed in the response body.
    data = resp.json()["data"]
    assert "access" not in data and "refresh" not in data


@pytest.mark.django_db
def test_login_rejects_unverified_user(client):
    User.objects.create_user(email="unverified@example.com", password=PASSWORD)
    resp = client.post(
        LOGIN_URL, {"email": "unverified@example.com", "password": PASSWORD}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "not_verified"


@pytest.mark.django_db
def test_login_rejects_bad_password(client, verified_user):
    resp = client.post(
        LOGIN_URL, {"email": "rider@example.com", "password": "wrong"}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "invalid_credentials"


@pytest.mark.django_db
def test_me_requires_authentication(client):
    resp = client.get(ME_URL)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_me_authenticates_via_cookie(client, verified_user):
    client.post(LOGIN_URL, {"email": "rider@example.com", "password": PASSWORD}, format="json")
    # APIClient persists Set-Cookie across requests, mimicking a browser.
    resp = client.get(ME_URL)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["email"] == "rider@example.com"
    assert data["role"] == User.Roles.PASSENGER


@pytest.mark.django_db
def test_refresh_rotates_refresh_token(client, verified_user):
    client.post(LOGIN_URL, {"email": "rider@example.com", "password": PASSWORD}, format="json")
    old_refresh = client.cookies["st_refresh"].value
    resp = client.post(REFRESH_URL)
    assert resp.status_code == 200
    assert resp.cookies["st_refresh"].value != old_refresh  # rotated
    assert resp.cookies["st_access"].value  # fresh access issued


@pytest.mark.django_db
def test_refresh_without_cookie_is_unauthenticated(client):
    resp = client.post(REFRESH_URL)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_email_verification_flow(client):
    user = User.objects.create_user(email="verify@example.com", password=PASSWORD)
    assert user.is_verified is False
    resp = client.post(VERIFY_URL, {"token": make_email_verify_token(user.id)}, format="json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.is_verified is True


@pytest.mark.django_db
def test_verify_rejects_tampered_token(client):
    resp = client.post(VERIFY_URL, {"token": "not-a-real-token"}, format="json")
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "token_invalid"
