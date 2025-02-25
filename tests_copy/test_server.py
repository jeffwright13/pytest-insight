import pytest
from fastapi.testclient import TestClient
from pytest_insight.server import app

client = TestClient(app)


@pytest.mark.parametrize(
    "metric",
    [
        "test.outcome.passed",
        "test.duration.elapsed",
        "test.warning.occurred",
        "test.pattern.slowed",
        "session.metric.started",
        "sut.metric.count",
        "rerun.metric.attempted",
        "history.metric.collected",
        "group.metric.formed",
    ],
)
def test_metric_queries(metric):
    """Verify each metric endpoint returns proper format."""
    response = client.post("/query", json={"target": metric})
    assert response.status_code == 200
    data = response.json()
    if data:  # Some metrics might return empty if no data
        assert isinstance(data, list)
        assert "target" in data[0]
        assert "datapoints" in data[0]
