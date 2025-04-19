"""Base classes and orchestrator for insight facets."""

class InsightFacet:
    """Base class for all insight facets."""
    def __init__(self, sessions):
        self.sessions = sessions
