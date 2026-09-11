"""Webhook ingestion and incremental sync (Stage 22, ADR-028).

A webhook endpoint is a public URL. Most of these tests are about what it
refuses, because an unverified receiver would let anyone forge the data every
metric in DevPulse is built on.
"""

import hashlib
import hmac
import json

import pytest

from app.core.webhook_security import is_valid_signature
from app.models.events import Repository, WebhookEvent
from app.services.webhooks import WebhookStatus, process_event, record_event

SECRET = "test-webhook-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def background_uses_the_test_database(monkeypatch, db_session):
    """Background processing opens its own session, which would otherwise reach
    the real database configured in .env. Point it at the test session, with a
    close() that does nothing so the fixture keeps ownership of the lifecycle."""
    class _Handle:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass

    monkeypatch.setattr("app.api.routes_webhooks.SessionLocal", lambda: _Handle())


@pytest.fixture
def webhooks_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "github_webhook_secret", SECRET, raising=False)


def _post(api_client, payload: dict, *, event="pull_request", delivery="d-1", secret=SECRET):
    body = json.dumps(payload).encode()
    return api_client.post(
        "/api/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body, secret),
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
            "Content-Type": "application/json",
        },
    )


class TestSignatureVerification:
    def test_a_correct_signature_validates(self):
        body = b'{"hello":"world"}'
        assert is_valid_signature(body, _sign(body), SECRET) is True

    def test_a_signature_from_another_secret_is_rejected(self):
        body = b'{"hello":"world"}'
        assert is_valid_signature(body, _sign(body, "other-secret"), SECRET) is False

    def test_an_altered_body_invalidates_the_signature(self):
        """This is the property that matters: the signature covers the payload,
        so a man-in-the-middle cannot change it and keep the header."""
        signature = _sign(b'{"amount":1}')
        assert is_valid_signature(b'{"amount":9999}', signature, SECRET) is False

    def test_a_missing_or_malformed_header_is_rejected(self):
        body = b"{}"
        assert is_valid_signature(body, None, SECRET) is False
        assert is_valid_signature(body, "md5=abc", SECRET) is False

    def test_no_secret_configured_means_nothing_validates(self):
        body = b"{}"
        assert is_valid_signature(body, _sign(body), "") is False


class TestEndpointRefusals:
    def test_unconfigured_webhooks_return_503(self, api_client):
        """Refusing is safer than accepting unverified payloads."""
        response = _post(api_client, {"action": "closed"})
        assert response.status_code == 503
        assert "GITHUB_WEBHOOK_SECRET" in response.json()["detail"]

    def test_a_forged_signature_is_rejected(self, api_client, webhooks_configured):
        body = json.dumps({"action": "closed"}).encode()
        response = api_client.post(
            "/api/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=" + "0" * 64,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "d-forged",
            },
        )
        assert response.status_code == 401

    def test_a_missing_delivery_id_is_rejected(self, api_client, webhooks_configured):
        body = json.dumps({"action": "closed"}).encode()
        response = api_client.post(
            "/api/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "",
            },
        )
        assert response.status_code == 400


class TestDeliveryHandling:
    def test_a_valid_delivery_is_accepted_and_recorded(
        self, api_client, db_session, webhooks_configured
    ):
        response = _post(api_client, {"action": "closed", "repository": {"full_name": "o/r"}})

        assert response.status_code == 202
        assert db_session.query(WebhookEvent).count() == 1

    def test_a_retried_delivery_is_recognised_not_double_counted(
        self, api_client, db_session, webhooks_configured
    ):
        """GitHub retries deliveries it believes failed."""
        payload = {"action": "closed", "repository": {"full_name": "o/r"}}
        _post(api_client, payload, delivery="same-id")
        second = _post(api_client, payload, delivery="same-id")

        assert second.json()["status"] == "duplicate"
        assert db_session.query(WebhookEvent).count() == 1

    def test_the_endpoint_responds_before_processing(self, api_client, webhooks_configured):
        """202, not 200: GitHub times out fast and retries on timeout, so doing
        the work first would turn a slow sync into duplicate deliveries."""
        response = _post(api_client, {"repository": {"full_name": "o/r"}})
        assert response.status_code == 202


class TestProcessing:
    def test_a_ping_is_acknowledged(self, db_session):
        event, _ = record_event(db_session, delivery_id="p1", event_type="ping", payload={})

        assert process_event(db_session, event) == WebhookStatus.PROCESSED

    def test_an_untracked_repository_is_ignored_not_created(self, db_session):
        """A webhook naming an unknown repository is not an instruction to start
        tracking it; accepting that would let anyone with the secret add repos."""
        event, _ = record_event(
            db_session, delivery_id="u1", event_type="pull_request",
            payload={"repository": {"full_name": "stranger/repo"}},
        )

        assert process_event(db_session, event) == WebhookStatus.IGNORED
        assert db_session.query(Repository).filter_by(full_name="stranger/repo").first() is None

    def test_an_unhandled_event_type_is_recorded_as_ignored(self, db_session, repository):
        event, _ = record_event(
            db_session, delivery_id="s1", event_type="star",
            payload={"repository": {"full_name": repository.full_name}},
        )

        assert process_event(db_session, event) == WebhookStatus.IGNORED
        assert "star" in event.detail

    def test_a_tracked_repository_is_marked_for_resync(self, db_session, repository):
        """The webhook is a SIGNAL that something changed. The REST API stays
        the source of truth, because a payload can be partial or out of order."""
        from app.services.timestamps import utc_now

        repository.last_synced_at = utc_now()
        db_session.commit()

        event, _ = record_event(
            db_session, delivery_id="t1", event_type="pull_request",
            payload={
                "repository": {"full_name": repository.full_name},
                "pull_request": {"updated_at": "2020-01-01T00:00:00Z"},
            },
        )

        assert process_event(db_session, event) == WebhookStatus.PROCESSED
        # Cursor rewound so the next sync definitely re-reads that window.
        assert repository.last_synced_at.year == 2020


class TestEventsEndpointIsProtected:
    def test_the_operator_listing_requires_auth_when_enabled(self, api_client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
        assert api_client.get("/api/webhooks/events").status_code == 401

    def test_the_receiver_stays_public_when_auth_is_enabled(
        self, api_client, monkeypatch, webhooks_configured
    ):
        """GitHub cannot present a bearer token; the signature is its auth."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
        assert _post(api_client, {"repository": {"full_name": "o/r"}}).status_code == 202
