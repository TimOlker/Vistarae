# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import json
import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Detect active environment (default: development)
APP_ENV = os.getenv("APP_ENV", "development").lower()

# Priority cascade: Later files override earlier files.
# Real OS/Docker environment variables always take the highest precedence.
ENV_FILES = (
    ".env",
    f".env.{APP_ENV}",
    f".env.{APP_ENV}.local",
    ".env.local",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/vistarae",
        description="Async PostgreSQL connection string",
    )
    DATABASE_URL_SYNC: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/vistarae",
        description="Sync PostgreSQL connection string for migrations/scripts",
    )

    # LLM Settings
    GEMINI_API_KEY: str = Field(default="", description="Google AI Studio Gemini API Key")
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash-lite", description="Gemini Flash-Lite model slug"
    )

    # Geocoding Settings
    NOMINATIM_BASE_URL: str = Field(
        default="https://nominatim.openstreetmap.org", description="OSM Nominatim base URL"
    )
    NOMINATIM_USER_AGENT: str = Field(
        default="VistaraeTravelEngine/1.0", description="OSM Nominatim custom User-Agent"
    )
    NOMINATIM_RATE_LIMIT_SEC: float = Field(
        default=1.0, description="Enforced sleep delay between non-cached Nominatim requests"
    )

    # Telemetry
    OTEL_SERVICE_NAME: str = Field(
        default="vistarae-backend", description="OpenTelemetry service name"
    )
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4317", description="OTLP collector gRPC endpoint"
    )
    OTEL_TRACES_ENABLED: bool = Field(default=True, description="Enable OpenTelemetry tracing")

    # JWT Authentication & Security
    JWT_SECRET_KEY: str = Field(
        default="vistarae-super-secret-jwt-key-change-in-production",
        description="Secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="Algorithm for JWT signing")
    JWT_EXPIRE_MINUTES: int = Field(
        default=60 * 24 * 30,  # 30 days
        description="Access token lifespan in minutes",
    )

    # Server & CORS
    APP_ENV: str = Field(default="development")
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8030)
    LOG_LEVEL: str = Field(default="INFO")
    CORS_ORIGINS: list[str] | str = Field(default=["*"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [s.strip() for s in v.split(",") if s.strip()]
        return v


settings = Settings()
