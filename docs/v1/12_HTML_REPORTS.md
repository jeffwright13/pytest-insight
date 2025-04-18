# pytest-insight HTML Reports

The pytest-insight HTML report generator creates comprehensive, interactive reports of test results that can be shared with team members and stakeholders. These standalone HTML files include detailed test information, visualizations, and analytics.

## Features

### Comprehensive Test Information
- Complete test session details
- Test outcomes with pass/fail status
- Duration metrics and execution times
- Captured output and error messages
- Test metadata and attributes

### Interactive Visualizations
- Test outcome distribution charts
- Duration analysis and performance trends
- Failure pattern analysis
- Test health metrics and stability indicators

### Shareable Format
- Self-contained HTML files with all necessary assets
- No external dependencies required to view
- Compatible with all modern browsers
- Easy to share via email or file sharing

### Customization Options
- Filter by date range or specific sessions
- Custom report titles
- Profile-specific reports
- Configurable output paths

## Installation

HTML report generation requires additional dependencies beyond the core pytest-insight package. Install them with:

```bash
# Install pytest-insight with HTML report dependencies
pip install pytest-insight[visualize]

# Or for all features
pip install pytest-insight[all]
```

## Usage

### Command Line

Generate HTML reports from the command line:

```bash
# Basic usage (generates report in current directory)
insight report generate

# Specify output location
insight report generate --output /path/to/report.html

# Filter by profile and time range
insight report generate --profile production --days 30

# Custom title
insight report generate --title "Weekly Test Report - Frontend Services"

# Specify session IDs
insight report generate --session abc123 --session def456

# Generate and automatically open in browser
insight report generate --open
```

### From the Dashboard

You can also generate reports directly from the pytest-insight dashboard:

1. Navigate to the "Export & Reports" section in the sidebar
2. Enter a custom title (optional)
3. Click "Generate Report"
4. Download the generated report

### Report Structure

The HTML report is organized into several sections:

1. **Summary**
   - Overall test statistics
   - Pass/fail rates
   - Duration metrics
   - Test session information

2. **Test Results**
   - Detailed list of all tests
   - Searchable and filterable
   - Expandable details for each test

3. **Visualizations**
   - Interactive charts and graphs
   - Test outcome distribution
   - Duration analysis
   - Failure patterns

4. **Session Details**
   - Information about test sessions
   - Environment details
   - Test system information
   - Timestamps and durations

## Integration with Storage Profiles

HTML reports respect the storage profile system, allowing you to generate reports for specific environments or configurations:

```bash
# Generate report for production profile
insight report generate --profile production

# Generate report for development profile
insight report generate --profile development
```

## User Tracking and Accountability

HTML reports include information about who generated the report and when, providing accountability in shared environments. This leverages the user tracking features of storage profiles to maintain a record of who created and accessed reports.

## Technical Implementation

The HTML report generator uses:

- Jinja2 templates for HTML generation
- Bootstrap for responsive design
- Plotly.js for interactive visualizations
- Markdown for formatting text content

## Customization

Advanced users can customize the report templates by modifying the files in the `pytest_insight/reports/templates` directory.
