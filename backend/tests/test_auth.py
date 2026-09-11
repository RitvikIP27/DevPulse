"""Authentication (Stage 23, ADR-027).

Security tests are mostly about what must NOT work: weak passwords, expired
tokens, tokens for deleted users, and unauthenticated access to data routes.
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.security import (
    ALGORITHM,
    InvalidToken,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.events import User
from app.services.timestamps import utc_now

VALID_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def auth_enabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key", raising=False)


@pytest.fixture
def existing_user(db_session):
    user = User(
        email="engineer@example.com",
        password_hash=hash_password(VALID_PASSWORD),
        display_name="Engineer",
        created_at=utc_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestPasswordHashing:
    def test_the_password_is_never_stored(self):
        digest = hash_password(VALID_PASSWORD)
        assert VALID_PASSWORD not in digest

    def test_the_same_password_hashes_differently_every_time(self):
        """A random salt per hash means two users with the same password do not
        share a digest, so cracking one does not crack the other."""
        assert hash_password(VALID_PASSWORD) != hash_password(VALID_PASSWORD)

    def test_verification_accepts_the_right_password(self):
        assert verify_password(VALID_PASSWORD, hash_password(VALID_PASSWORD))

    def test_verification_rejects_the_wrong_password(self):
        assert not verify_password("wrong", hash_password(VALID_PASSWORD))

    def test_a_malformed_stored_hash_fails_closed(self):
        """Never raise into a request; a corrupt row must deny, not crash."""
        assert verify_password(VALID_PASSWORD, "not-a-bcrypt-hash") is False

    def test_an_over_long_password_is_rejected_rather_than_truncated(self):
        """bcrypt silently ignores bytes past 72. Accepting would quietly weaken
        a password the user believes is long."""
        with pytest.raises(ValueError, match="72 bytes"):
            hash_password("a" * 100)


class TestTokens:
    def test_a_token_round_trips_to_its_user_id(self, auth_enabled):
        assert decode_access_token(create_access_token(42)) == 42

    def test_an_expired_token_is_rejected(self, auth_enabled):
        with pytest.raises(InvalidToken):
            decode_access_token(create_access_token(42, expires_minutes=-1))

    def test_a_token_signed_with_another_key_is_rejected(self, auth_enabled):
        forged = jwt.encode(
            {"sub": "42", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "a-different-secret",
            algorithm=ALGORITHM,
        )
        with pytest.raises(InvalidToken):
            decode_access_token(forged)

    def test_a_tampered_token_is_rejected(self, auth_enabled):
        token = create_access_token(42)
        with pytest.raises(InvalidToken):
            decode_access_token(token[:-3] + "aaa")

    def test_a_token_carries_no_secret(self, auth_enabled):
        """A JWT is signed, not encrypted — anyone can read it."""
        payload = jwt.get_unverified_claims(create_access_token(42))
        assert set(payload) == {"sub", "exp", "iat"}


class TestRegistrationAndLogin:
    def test_the_first_account_can_be_created(self, api_client):
        response = api_client.post(
            "/api/auth/register",
            json={"email": "first@example.com", "password": VALID_PASSWORD},
        )

        assert response.status_code == 201
        assert response.json()["access_token"]

    def test_registration_closes_once_an_account_exists(self, api_client, existing_user):
        """An open endpoint that mints accounts would make auth pointless."""
        response = api_client.post(
            "/api/auth/register",
            json={"email": "second@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 403

    def test_a_short_password_is_rejected_by_validation(self, api_client):
        response = api_client.post(
            "/api/auth/register", json={"email": "a@example.com", "password": "short"}
        )
        assert response.status_code == 422

    def test_login_succeeds_with_the_right_password(self, api_client, existing_user):
        response = api_client.post(
            "/api/auth/login",
            json={"email": "engineer@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"

    def test_login_is_case_insensitive_on_email(self, api_client, existing_user):
        response = api_client.post(
            "/api/auth/login",
            json={"email": "ENGINEER@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 200

    def test_an_unknown_email_and_a_wrong_password_are_indistinguishable(
        self, api_client, existing_user
    ):
        """Different messages would let anyone enumerate registered emails."""
        unknown = api_client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": VALID_PASSWORD},
        )
        wrong = api_client.post(
            "/api/auth/login",
            json={"email": "engineer@example.com", "password": "wrong-password"},
        )

        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["detail"] == wrong.json()["detail"]

    def test_an_inactive_account_cannot_log_in(self, api_client, db_session, existing_user):
        existing_user.is_active = False
        db_session.commit()

        response = api_client.post(
            "/api/auth/login",
            json={"email": "engineer@example.com", "password": VALID_PASSWORD},
        )
        assert response.status_code == 401


class TestRouteProtection:
    def test_data_routes_are_open_when_auth_is_disabled(self, api_client):
        """A local single-user install is not forced through a login."""
        assert api_client.get("/api/repositories").status_code == 200

    def test_data_routes_reject_anonymous_callers_when_auth_is_enabled(
        self, api_client, auth_enabled
    ):
        for path in (
            "/api/repositories", "/api/metrics/dora", "/api/deliveries",
            "/api/bottlenecks", "/api/conflicts", "/api/anomalies",
            "/api/health-score", "/api/analysis/candidates",
            "/api/ingest/jobs", "/api/webhooks/events",
        ):
            assert api_client.get(path).status_code == 401, path

    def test_every_protected_get_route_is_covered_by_the_check_above(self):
        """Guards the guard: if a new GET route is added to a protected router,
        this fails until it is added to the assertion list. Without it the test
        above would quietly stop covering the whole surface."""
        from app.main import app
        from app.core.dependencies import current_user

        protected_gets = {
            route.path
            for route in app.routes
            if getattr(route, "path", "").startswith("/api")
            and "GET" in getattr(route, "methods", set())
            and any(
                getattr(d, "dependency", None) is current_user
                for d in getattr(route, "dependencies", [])
            )
            and "{" not in route.path  # path-parameter routes need real ids
        }
        asserted = {
            "/api/repositories", "/api/metrics/dora", "/api/deliveries",
            "/api/bottlenecks", "/api/conflicts", "/api/anomalies",
            "/api/health-score", "/api/analysis/candidates",
            "/api/ingest/jobs", "/api/webhooks/events",
        }
        assert protected_gets == asserted, (
            "A protected GET route is not covered by the anonymous-access test: "
            f"{protected_gets ^ asserted}"
        )

    def test_a_valid_token_is_accepted(self, api_client, auth_enabled, existing_user):
        token = create_access_token(existing_user.id)

        response = api_client.get(
            "/api/repositories", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_a_token_for_a_deleted_user_stops_working(
        self, api_client, db_session, auth_enabled, existing_user
    ):
        """A signature check alone would still accept this."""
        token = create_access_token(existing_user.id)
        db_session.delete(existing_user)
        db_session.commit()

        response = api_client.get(
            "/api/repositories", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    def test_a_token_for_a_deactivated_user_stops_working(
        self, api_client, db_session, auth_enabled, existing_user
    ):
        token = create_access_token(existing_user.id)
        existing_user.is_active = False
        db_session.commit()

        response = api_client.get(
            "/api/repositories", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    def test_a_non_bearer_scheme_is_rejected(self, api_client, auth_enabled, existing_user):
        token = create_access_token(existing_user.id)

        response = api_client.get(
            "/api/repositories", headers={"Authorization": f"Basic {token}"}
        )
        assert response.status_code == 401

    def test_health_and_auth_status_stay_public(self, api_client, auth_enabled):
        """Liveness probes cannot authenticate, and the UI needs status to know
        whether to render a login screen."""
        assert api_client.get("/health").status_code == 200
        assert api_client.get("/api/auth/status").status_code == 200


class TestAuthStatus:
    def test_reports_whether_any_account_exists(self, api_client, db_session):
        assert api_client.get("/api/auth/status").json()["has_users"] is False

        db_session.add(User(
            email="a@example.com", password_hash=hash_password(VALID_PASSWORD),
            created_at=utc_now(),
        ))
        db_session.commit()

        assert api_client.get("/api/auth/status").json()["has_users"] is True


class TestEmailHandling:
    def test_an_internal_domain_is_accepted(self, api_client):
        """DevPulse is self-hosted and often runs on private domains. Rejecting
        admin@devpulse.local because it has no MX record would be wrong."""
        response = api_client.post(
            "/api/auth/register",
            json={"email": "admin@devpulse.local", "password": VALID_PASSWORD},
        )
        assert response.status_code == 201

    def test_a_malformed_address_is_still_rejected(self, api_client):
        response = api_client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": VALID_PASSWORD},
        )
        assert response.status_code == 422

    def test_email_is_normalised_to_lower_case(self, api_client, db_session):
        api_client.post(
            "/api/auth/register",
            json={"email": "Mixed.Case@Example.COM", "password": VALID_PASSWORD},
        )
        assert db_session.query(User).one().email == "mixed.case@example.com"


class TestEmailSyntaxValidation:
    @pytest.mark.parametrize(
        "address",
        [
            "user@example.com",
            "user.name+tag@sub.example.co.uk",
            "admin@devpulse.local",   # internal domain
            "dev@localhost",          # single-label domain
        ],
    )
    def test_valid_addresses_are_accepted(self, api_client, db_session, address):
        from app.models.events import User as U

        db_session.query(U).delete()
        db_session.commit()
        response = api_client.post(
            "/api/auth/register", json={"email": address, "password": VALID_PASSWORD}
        )
        assert response.status_code == 201, address

    @pytest.mark.parametrize(
        "address",
        ["no-at-sign", "@example.com", "user@", "user@.com", "user..name@example.com", "user@exa mple.com"],
    )
    def test_malformed_addresses_are_rejected(self, api_client, address):
        response = api_client.post(
            "/api/auth/register", json={"email": address, "password": VALID_PASSWORD}
        )
        assert response.status_code == 422, address
