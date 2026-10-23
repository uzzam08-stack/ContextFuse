"""
ContextFuse – AWS Lambda Handler.

Wraps the FastAPI application using Mangum for AWS Lambda & Amazon API Gateway.
Supports HTTP API (payload v2.0) and REST API (payload v1.0).
"""

from mangum import Mangum
from app.main import app

# Lambda entry point: handler(event, context)
handler = Mangum(app, lifespan="off")
