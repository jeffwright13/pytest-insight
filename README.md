## API Documentation

pytest-insight provides a RESTful API powered by FastAPI that can be explored using interactive documentation:

### Swagger UI
Access the interactive API documentation at:
```bash
http://localhost:8000/docs
```

The Swagger UI provides:
- Complete API endpoint listing
- Interactive "Try it out" functionality
- Request/response examples
- Schema information for all metrics
- Filter parameter documentation

### ReDoc
Alternative API documentation view:
```bash
http://localhost:8000/redoc
```

### OpenAPI Schema
Raw OpenAPI specification:
```bash
http://localhost:8000/openapi.json
```

### Available Endpoints

- `GET /`: Health check endpoint
- `GET /health`: Detailed health status
- `GET /search`: List available metrics
- `POST /query`: Query metric data

### Query Examples

Query test outcomes:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"target": "test.outcome.passed"}'
```

Query with filters:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "target": "test.duration.trend",
    "filters": {
      "sut": "my-service",
      "days": 7
    }
  }'
```

See [docs/examples/curls.md](docs/examples/curls.md) for more API examples.
