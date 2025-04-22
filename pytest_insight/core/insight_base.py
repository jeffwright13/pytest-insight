class Insight:
    """
    Base class for all insight/facet classes in pytest-insight.
    Defines the expected interface for analytics, reporting, and query facets.
    Methods not implemented by a subclass will raise NotImplementedError.
    """

    def insight(self, kind: str):
        """Return insight data for the specified kind."""
        raise NotImplementedError("Subclasses must implement .insight()")

    def tests(self):
        """Return test-level insight object or data."""
        raise NotImplementedError("Subclasses must implement .tests()")

    def sessions(self):
        """Return session-level insight object or data."""
        raise NotImplementedError("Subclasses must implement .sessions()")

    def summary(self):
        """Return summary stats or metrics for the insight."""
        raise NotImplementedError("Subclasses must implement .summary()")

    def reliability(self):
        """Return reliability/flakiness metrics for the insight."""
        raise NotImplementedError("Subclasses must implement .reliability()")

    def trends(self):
        """Return trend data (performance, reliability, etc.)."""
        raise NotImplementedError("Subclasses must implement .trends()")

    def comparison(self):
        """Return comparison analytics (between versions, times, etc.)."""
        raise NotImplementedError("Subclasses must implement .comparison()")

    def meta(self):
        """Return meta-analytics or metadata for the insight."""
        raise NotImplementedError("Subclasses must implement .meta()")

    def predict(self):
        """Return predictive analytics for the insight."""
        raise NotImplementedError("Subclasses must implement .predict()")

    def temporal(self):
        """Return time-based/trend analytics for the insight."""
        raise NotImplementedError("Subclasses must implement .temporal()")
