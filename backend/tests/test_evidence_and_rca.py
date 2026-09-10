"""Evidence package assembly and AI RCA (Stages 15 and 16).

The AI path is exercised through a fake provider. Tests must never call a real
model: it would be slow, cost money, and make the suite non-deterministic — and
what is being tested here is DevPulse's handling of model output, not the model.
"""

from datetime import timedelta

import pytest

from app.models.events import Deployment, Incident, RcaAnalysis, RuntimeObservation
from app.schemas.evidence import EvidencePackage
from app.schemas.rca import Hypothesis, RcaConfidence, RcaResult
from app.services.ai.provider import AIUnavailable
from app.services.ai.rca import check_integrity, generate_rca
from app.services.deployments import PROVIDER_CONFIGURED_WORKFLOW, DeploymentStatus
from app.services.evidence import build_evidence
from tests.conftest import NOW

MERGE_SHA = "abc123def456"


@pytest.fixture
def monitoring_connected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "prometheus_url", "http://prometheus.test", raising=False)


@pytest.fixture
def deployment(db_session, repository, runs):
    pr = runs.add_merged_pr(number=482, merged_minutes_ago=140, opened_minutes_ago=440)
    pr.merge_commit_sha = MERGE_SHA
    pr.author_login = "octocat"
    db_session.commit()

    run = runs.add(workflow_name="CI", conclusion="success", started_minutes_ago=139)
    run.head_sha = MERGE_SHA
    db_session.commit()

    row = Deployment(
        repository_id=repository.id, provider=PROVIDER_CONFIGURED_WORKFLOW,
        external_id="dep-1", environment="production", is_production=True,
        commit_sha=MERGE_SHA, status=DeploymentStatus.SUCCESS,
        started_at=NOW - timedelta(minutes=68), finished_at=NOW - timedelta(minutes=65),
    )
    db_session.add(row)
    db_session.commit()
    return row


def _degrade(db, repository, deployment):
    anchor = deployment.finished_at
    for offset, value in enumerate([0.8, 0.7, 0.9, 0.8], start=1):
        db.add(RuntimeObservation(
            repository_id=repository.id, provider="prometheus", environment="production",
            metric="error_rate_pct", value=value, observed_at=anchor - timedelta(minutes=offset),
        ))
    for offset, value in enumerate([18.4, 17.9, 19.1, 18.0], start=1):
        db.add(RuntimeObservation(
            repository_id=repository.id, provider="prometheus", environment="production",
            metric="error_rate_pct", value=value, observed_at=anchor + timedelta(minutes=offset),
        ))
    db.commit()


class FakeProvider:
    """Stands in for a model. Returns whatever the test wants it to return."""

    name = "fake"
    model = "fake-model-1"

    def __init__(self, result=None, error=None, configured=True):
        self._result = result
        self._error = error
        self._configured = configured
        self.calls = 0

    def is_configured(self) -> bool:
        return self._configured

    def generate_rca(self, evidence, prompt):
        self.calls += 1
        if self._error:
            raise self._error
        self.received_prompt = prompt
        return self._result


def _result(**overrides) -> RcaResult:
    base = dict(
        summary="Error rate rose after a successful deployment.",
        likely_cause="A regression in the deployed change, correlated with the release.",
        confidence=RcaConfidence.MEDIUM,
        affected_stage="RUNTIME",
        impact="Users saw elevated failures.",
        observed_facts=["Error rate moved from 0.8 to 18.4."],
        inferences=["The change is the most likely source."],
        alternative_hypotheses=[
            Hypothesis(
                hypothesis="An external dependency degraded.",
                supporting_evidence=["Timing alone does not exclude it."],
                confidence=RcaConfidence.LOW,
            )
        ],
        recommended_investigation=["Compare error signatures before and after."],
        recommended_actions=["Inspect the payment validation path in abc123def456."],
        unknowns=["Whether the deployment caused the change."],
    )
    base.update(overrides)
    return RcaResult(**base)


class TestEvidencePackage:
    def test_is_built_from_deterministic_engines(self, db_session, repository, deployment):
        evidence = build_evidence(db_session, deployment.id)

        assert isinstance(evidence, EvidencePackage)
        assert evidence.commit_sha == MERGE_SHA
        assert evidence.pull_request_number == 482
        assert evidence.author_login == "octocat"
        assert evidence.stages, "stages come from the delivery trace"

    def test_carries_conflicts_when_runtime_degraded(
        self, db_session, repository, deployment, monitoring_connected
    ):
        _degrade(db_session, repository, deployment)

        evidence = build_evidence(db_session, deployment.id)

        assert evidence.conflicts
        assert evidence.runtime.available is True

    def test_states_its_own_limitations(self, db_session, repository, deployment):
        """The model is told what the evidence cannot answer, rather than
        being left to discover it."""
        evidence = build_evidence(db_session, deployment.id)

        assert evidence.known_limitations
        assert any("cannot determine" in item for item in evidence.known_limitations)
        assert any("elapsed time, not effort" in item for item in evidence.known_limitations)

    def test_hash_is_stable_for_identical_facts(self, db_session, repository, deployment):
        first = build_evidence(db_session, deployment.id)
        second = build_evidence(db_session, deployment.id)

        # generated_at differs between the two; the hash must not.
        assert first.evidence_hash == second.evidence_hash

    def test_hash_changes_when_the_facts_change(
        self, db_session, repository, deployment, monitoring_connected
    ):
        before = build_evidence(db_session, deployment.id).evidence_hash
        _degrade(db_session, repository, deployment)
        after = build_evidence(db_session, deployment.id).evidence_hash

        assert before != after

    def test_unknown_deployment_returns_none(self, db_session):
        assert build_evidence(db_session, 9999) is None


class TestWithoutAI:
    def test_absence_of_a_provider_still_returns_the_evidence_hash(
        self, db_session, deployment
    ):
        """AI is an interpretation layer. Its absence must not hide the facts."""
        response = generate_rca(db_session, deployment.id, provider=FakeProvider(configured=False))

        assert response.available is False
        assert "deterministically" in response.unavailable_reason
        assert response.evidence_hash

    def test_a_provider_failure_is_reported_not_swallowed(self, db_session, deployment):
        provider = FakeProvider(error=AIUnavailable("Anthropic rejected the API key."))

        response = generate_rca(db_session, deployment.id, provider=provider)

        assert response.available is False
        assert "rejected the API key" in response.unavailable_reason

    def test_a_refusal_does_not_produce_a_fabricated_analysis(self, db_session, deployment):
        provider = FakeProvider(error=AIUnavailable("The model declined to analyse this evidence."))

        response = generate_rca(db_session, deployment.id, provider=provider)

        assert response.result is None


class TestWithAI:
    def test_a_successful_analysis_is_returned_and_stored(self, db_session, deployment):
        provider = FakeProvider(result=_result())

        response = generate_rca(db_session, deployment.id, provider=provider)

        assert response.available is True
        assert response.result.confidence is RcaConfidence.MEDIUM
        assert db_session.query(RcaAnalysis).count() == 1

    def test_identical_evidence_reuses_the_stored_analysis(self, db_session, deployment):
        """Analysis costs money. Identical facts must not be paid for twice."""
        provider = FakeProvider(result=_result())

        generate_rca(db_session, deployment.id, provider=provider)
        second = generate_rca(db_session, deployment.id, provider=provider)

        assert provider.calls == 1
        assert second.cached is True
        assert db_session.query(RcaAnalysis).count() == 1

    def test_force_bypasses_the_cache(self, db_session, deployment):
        provider = FakeProvider(result=_result())

        generate_rca(db_session, deployment.id, provider=provider)
        generate_rca(db_session, deployment.id, provider=provider, force=True)

        assert provider.calls == 2

    def test_the_stored_analysis_records_how_it_was_produced(self, db_session, deployment):
        """Reproducibility: an analysis must be traceable to its inputs."""
        generate_rca(db_session, deployment.id, provider=FakeProvider(result=_result()))

        record = db_session.query(RcaAnalysis).one()
        assert record.model == "fake-model-1"
        assert record.prompt_version
        assert record.evidence_hash
        assert record.evidence_json

    def test_the_model_receives_only_the_evidence_package(self, db_session, deployment):
        provider = FakeProvider(result=_result())

        generate_rca(db_session, deployment.id, provider=provider)

        assert "evidence_hash" in provider.received_prompt
        assert "known_limitations" in provider.received_prompt


class TestIntegrityGuard:
    def test_a_number_absent_from_the_evidence_is_flagged(self, db_session, deployment):
        """The failure that matters most is a confident figure the model wrote
        rather than read."""
        evidence = build_evidence(db_session, deployment.id)
        fabricated = _result(
            observed_facts=["The error rate reached 94.7 percent across 3312 requests."]
        )

        warnings = check_integrity(fabricated, evidence)

        assert warnings
        assert any("94.7" in warning for warning in warnings)

    def test_numbers_present_in_the_evidence_are_not_flagged(
        self, db_session, repository, deployment, monitoring_connected
    ):
        _degrade(db_session, repository, deployment)
        evidence = build_evidence(db_session, deployment.id)

        # The package carries the MEDIAN of the samples, not the raw readings.
        # A model quoting 18.4 (a raw sample it was never given) is correctly
        # flagged; only the figure actually present passes.
        after_median = next(
            shift.after_value for shift in evidence.runtime.shifts
            if shift.metric == "error_rate_pct"
        )
        grounded = _result(observed_facts=[f"Error rate moved from 0.8 to {after_median}."])

        assert check_integrity(grounded, evidence) == []

    def test_warnings_are_surfaced_on_the_response(self, db_session, deployment):
        provider = FakeProvider(result=_result(summary="Latency hit 8421 milliseconds."))

        response = generate_rca(db_session, deployment.id, provider=provider)

        assert response.integrity_warnings
        # The analysis is still returned; the reader is warned, not blocked.
        assert response.available is True


class TestApi:
    def test_evidence_endpoint_returns_the_package(self, api_client, deployment):
        response = api_client.get(f"/api/analysis/evidence/{deployment.id}")

        assert response.status_code == 200
        assert response.json()["commit_sha"] == MERGE_SHA

    def test_evidence_for_an_unknown_deployment_is_404(self, api_client):
        assert api_client.get("/api/analysis/evidence/9999").status_code == 404

    def test_rca_endpoint_reports_unavailable_without_a_key(self, api_client, deployment):
        response = api_client.post(f"/api/analysis/rca/{deployment.id}")

        assert response.status_code == 200
        assert response.json()["available"] is False

    def test_candidates_rank_conflicts_first(
        self, api_client, db_session, repository, deployment, monitoring_connected
    ):
        _degrade(db_session, repository, deployment)

        response = api_client.get("/api/analysis/candidates")

        assert response.status_code == 200
        candidates = response.json()["candidates"]
        assert candidates[0]["conflict_count"] >= 1


class TestEvidenceIsInternallyConsistent:
    """The delivery trace only knows source control, so it marks DEPLOYMENT,
    RUNTIME and INCIDENT unobserved regardless of other providers. The evidence
    package must reconcile that before a model ever sees it."""

    def test_runtime_is_not_reported_unobserved_while_a_runtime_conflict_exists(
        self, db_session, repository, deployment, monitoring_connected
    ):
        _degrade(db_session, repository, deployment)

        evidence = build_evidence(db_session, deployment.id)

        runtime_stage = next(s for s in evidence.stages if s.stage == "RUNTIME")
        assert evidence.conflicts, "precondition: a runtime conflict was detected"
        assert runtime_stage.status != "NOT_OBSERVED"

    def test_deployment_stage_reflects_the_actual_deployment(
        self, db_session, repository, deployment
    ):
        evidence = build_evidence(db_session, deployment.id)

        stage = next(s for s in evidence.stages if s.stage == "DEPLOYMENT")
        assert stage.status == "SUCCESS"
        assert "production" in stage.detail

    def test_incident_stage_reflects_associated_incidents(
        self, db_session, repository, deployment, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "pagerduty_token", "t", raising=False)
        monkeypatch.setattr(settings, "pagerduty_service_ids", "P1", raising=False)
        db_session.add(Incident(
            repository_id=repository.id, provider="pagerduty", external_id="1",
            title="Payment failures", status="TRIGGERED",
            started_at=deployment.finished_at + timedelta(minutes=4),
        ))
        db_session.commit()

        evidence = build_evidence(db_session, deployment.id)

        stage = next(s for s in evidence.stages if s.stage == "INCIDENT")
        assert stage.status == "FAILED"
        assert "1 incident" in stage.detail

    def test_runtime_stays_unobserved_when_no_provider_is_connected(
        self, db_session, deployment
    ):
        evidence = build_evidence(db_session, deployment.id)

        runtime_stage = next(s for s in evidence.stages if s.stage == "RUNTIME")
        assert runtime_stage.status == "NOT_OBSERVED"
