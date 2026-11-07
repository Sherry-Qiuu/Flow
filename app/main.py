"""Uvicorn entry point: ``uvicorn app.main:app``."""

from service.app import create_app

app = create_app()
