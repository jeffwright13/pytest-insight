# pytest-insight Dashboard

The pytest-insight dashboard provides a visual interface for exploring test insights and predictive analytics. It offers an intuitive way to visualize test health metrics, stability trends, and predictive insights from your test data.

## Features

### Test Health Metrics
- Pass rate and trends
- Flaky test detection
- Duration analysis
- Overall health score

### Stability Trends
- Pass rate over time
- Flaky rate over time
- Visual trend analysis

### Predictive Insights
- **Failure Predictions**: Identify tests likely to fail in upcoming runs
- **Anomaly Detection**: Find tests with unusual behavior patterns
- **Stability Forecast**: Predict how test stability will evolve

## Installation

The dashboard requires additional dependencies beyond the core pytest-insight package. Install them with:

```bash
# Install pytest-insight with dashboard dependencies
pip install pytest-insight[dashboard]

# Or for all features
pip install pytest-insight[all]
```

## Usage

### Command Line

Launch the dashboard from the command line:

```bash
# Basic usage
insight dashboard launch

# Specify a port
insight dashboard launch --port 8502

# Use a specific storage profile
insight dashboard launch --profile production

# Launch without opening browser automatically
insight dashboard launch --no-browser
```

### Dashboard Interface

1. **Configuration**
   - Select a storage profile from the sidebar
   - Filter by System Under Test (SUT)
   - Choose a time range for analysis

2. **Health Metrics**
   - View key test health indicators
   - See outcome distribution

3. **Stability Trends**
   - Analyze pass rate and flaky rate over time
   - Identify patterns and trends

4. **Predictive Insights**
   - Explore failure predictions for high-risk tests
   - Investigate anomalous test behavior
   - View stability forecasts and contributing factors

## Integration with Core API

The dashboard is built on top of the pytest-insight Core API, using the same fluent interface pattern. It leverages the Query, Analysis, and Predictive components to provide a rich visual experience.

```python
# Example of the underlying API used by the dashboard
from pytest_insight.core.core_api import InsightAPI

# Create API instance with profile
api = InsightAPI(profile_name="production")

# Get predictive analytics
predictive = api.predictive()
predictions = predictive.failure_prediction(days_ahead=7)
```

## Customization

The dashboard is built with Streamlit, making it easy to customize and extend. You can modify the dashboard code in `pytest_insight/web/dashboard.py` to add additional visualizations or features.

## Requirements

- Python 3.9+
- streamlit>=1.22.0
- pandas>=1.5.0
- plotly>=5.13.0
- scikit-learn>=1.2.0 (for predictive analytics)
