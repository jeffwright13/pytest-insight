from pytest_insight.insight_api import InsightAPI
from pytest_insight.storage import ProfileManager

# 1. Initialize the profile manager
profile_manager = ProfileManager()  # defaults to "default"
profile_manager.switch_profile("trends")  # switch to "trends" profile

# 2. Use the profile to initialize the API
api = InsightAPI(profile=profile_manager.active_profile_name)

# 3. Now all API operations are scoped to this profile's storage/config
summary = api.summary().get()
# api.tests().filter(name="test_foo").insight("flakiness")
# api.over_time(days=30).insight("trend")
# api.compare(sut_a="service", sut_b="service2").insight("regression")
# api.trend().insight("trend")
# api.predictive().insight("predictive_failure")
# api.meta().insight("maintenance_burden")
# api.session("session1").insight("summary")
