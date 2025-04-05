The pytest-insight Dynamic API
What you're looking at is the Swagger UI documentation for the pytest-insight Dynamic API, which is a REST API that's been automatically generated from your pytest-insight Python classes. This API is a powerful feature that allows you to access your pytest test insights through HTTP requests.

Key Components
Introspective API Generation
Located in /pytest_insight/rest_api/introspective_api.py
Uses Python's introspection capabilities to dynamically generate FastAPI endpoints
Automatically categorizes endpoints based on method name patterns (Query, Comparison, Analysis, etc.)
Creates Pydantic models for request parameters with appropriate validation
Server Launcher
Located in /pytest_insight/utils/server_launcher_introspect.py
Provides a command-line interface to start the API server
Configures database paths, host, port, and other settings
Runs the API using uvicorn
Web Dashboard
Located in /web_dashboard.py
Provides a Flask-based web interface for interacting with the pytest-insight API
Allows management of storage profiles, executing queries, and viewing insights
Complements the API with a user-friendly interface
How It Works
The Dynamic API uses introspection to:

Examine your Python classes (Query, Comparison, Analysis, Insights)
Identify their methods and parameters
Generate corresponding REST endpoints with proper parameter validation
Organize endpoints into logical categories
Create interactive Swagger documentation
This approach means that as you add new methods to your Python classes, the API automatically exposes them without requiring manual updates to the API code.

API Categories
The API is organized into several operation categories that mirror your core pytest-insight functionality:

Query Operations - Finding and filtering test sessions
Comparison Operations - Comparing test results between versions/times
Analysis Operations - Extracting insights and metrics
Filtering Operations - Filtering test results
Introspect API - Meta-endpoints that provide information about the API itself
Integration with Storage Profiles
The API fully supports your storage profile system, allowing you to:

Query data from specific profiles
Compare data across different profiles
Analyze test results from any profile
Switch between profiles seamlessly
This aligns with your goal of using named profiles to abstract away storage details, which is particularly useful for your Jenkins/Docker CI/CD environment.

Relationship to the Python API
This REST API is a direct reflection of your Python fluent API, providing the same capabilities but through HTTP requests. It's designed to complement, not replace, the Python API, giving you flexibility in how you access your test data.

Would you like me to explain any specific aspect of the API in more detail, or would you like to see how to use it for a particular use case?

Feedback submitted
Generating
