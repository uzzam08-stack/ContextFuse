"""
ContextFuse – FastAPI application entry point.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.routers.main import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("ContextFuse backend starting…")
    yield
    print("ContextFuse backend shutting down.")


app = FastAPI(
    title="ContextFuse",
    description="The Context Safety Gate for AI Agents — AWS Agent Experience Hackathon",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "ContextFuse",
        "tagline": "The Context Safety Gate for AI Agents",
        "docs": "/docs",
    }
