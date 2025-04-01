graph TD
    A[pytest] -->|writes| B[local JSON]
    B -->|read by| C[FastAPI server]
    C -->|serves| D[Grafana JSON API]
    D -->|displays| E[Local Dashboard]
