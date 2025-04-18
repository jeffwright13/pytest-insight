# pytest-insight API Explorer

The API Explorer is a tool for exploring and documenting the pytest-insight API. It provides an interactive web interface for:

1. **API Documentation**: Auto-generated documentation for all API endpoints
2. **Dashboard**: Visual exploration of test data through the REST API
3. **API Testing**: Interactive testing of API endpoints

## Purpose

The API Explorer serves as a lower-level API documentation and exploration tool, complementing the main Streamlit dashboard. While the Streamlit dashboard provides high-level visualizations and insights, the API Explorer focuses on:

- Documenting the REST API endpoints
- Allowing developers to explore the raw API capabilities
- Providing a testing ground for API integration
- Demonstrating the underlying API architecture

## Usage

You can launch the API Explorer using the CLI:

```bash
# Launch the API Explorer with default settings
insight api-explorer launch

# Specify a custom port
insight api-explorer launch --port 8080

# Use a specific storage profile
insight api-explorer launch --profile production

# Start without opening a browser
insight api-explorer launch --no-browser
```

## Key Features

### 1. Interactive API Documentation

The API Explorer provides auto-generated documentation for all API endpoints using FastAPI's built-in Swagger UI. This documentation is available at `/docs` and includes:

- Endpoint descriptions
- Request/response schemas
- Example requests
- Interactive testing capabilities

### 2. Dashboard

The API Explorer includes a dashboard at `/dashboard` that provides:

- Session exploration
- Query building
- Analysis visualization
- Comparison tools

### 3. API Testing

You can test API endpoints directly from the browser using:

- Swagger UI at `/docs`
- ReDoc at `/redoc`
- Direct API calls to endpoints

## Integration with pytest-insight

The API Explorer is fully integrated with the pytest-insight ecosystem:

- Uses the same storage profiles as the main CLI
- Accesses the same test data
- Provides a different view of the same underlying functionality

For a comprehensive overview of the pytest-insight architecture, please refer to [02_ARCHITECTURE_OVERVIEW.md](./02_ARCHITECTURE_OVERVIEW.md).

For a conceptual understanding of the four layers, see [01_CONCEPTUAL_FRAMEWORK.md](./01_CONCEPTUAL_FRAMEWORK.md).

## Technical Details

The API Explorer is built using:

- **FastAPI**: For the REST API framework
- **Uvicorn**: As the ASGI server
- **Jinja2**: For templating
- **Introspection**: Auto-generates API endpoints from the pytest-insight codebase

## Relationship to Streamlit Dashboard

The API Explorer complements the Streamlit dashboard:

| Feature | API Explorer | Streamlit Dashboard |
|---------|-------------|---------------------|
| **Focus** | API documentation & exploration | High-level insights & visualization |
| **Target Users** | Developers & API users | Test engineers & managers |
| **Technical Level** | Lower-level API access | Higher-level abstracted views |
| **Customization** | Raw API access | Pre-built visualizations |
| **Integration** | API testing & documentation | Data analysis & reporting |
