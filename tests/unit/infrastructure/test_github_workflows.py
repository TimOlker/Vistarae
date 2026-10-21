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

"""Unit tests for GitHub Actions OIDC CI/CD workflows (T043, REQ-CICD-001 through REQ-CICD-018).

Validates workflow schema structure, keyless OIDC permission configuration,
absence of hardcoded AWS secrets, path filter triggers, caching headers,
OpenAPI contract drift gates, and single post-deployment health verification.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_WORKFLOWS_DIR = _REPO_ROOT / ".github" / "workflows"
_CI_FILE = _WORKFLOWS_DIR / "ci.yml"
_DEPLOY_FILE = _WORKFLOWS_DIR / "deploy.yml"


def test_workflow_files_exist():
    """Verifies that both ci.yml and deploy.yml exist in .github/workflows/."""
    assert _CI_FILE.exists(), f"Missing CI workflow file: {_CI_FILE}"
    assert _DEPLOY_FILE.exists(), f"Missing Deploy workflow file: {_DEPLOY_FILE}"


def test_ci_workflow_schema_and_gates():
    """Validates CI workflow triggers, services, and quality gates (REQ-CICD-004 to REQ-CICD-011)."""
    with open(_CI_FILE, encoding="utf-8") as f:
        ci_yaml = yaml.safe_load(f)

    # 1. Triggers and path filtering (REQ-CICD-004)
    trigger_config = ci_yaml.get("on") or ci_yaml.get(True)
    assert trigger_config is not None
    assert "push" in trigger_config
    assert "pull_request" in trigger_config
    paths = trigger_config["pull_request"]["paths"]
    assert any("services/**" in p for p in paths)
    assert any("packages/core/**" in p for p in paths)
    assert any("frontend/**" in p for p in paths)
    assert any("template.yaml" in p for p in paths)

    # 2. Backend Job & PostGIS Service Container (REQ-CICD-005)
    jobs = ci_yaml["jobs"]
    assert "backend-quality-and-tests" in jobs
    backend_job = jobs["backend-quality-and-tests"]
    assert "services" in backend_job
    assert "postgres" in backend_job["services"]
    postgres_service = backend_job["services"]["postgres"]
    assert "postgis/postgis:16-3.4" in postgres_service["image"]

    # 3. Steps: Ruff, OpenAPI drift, Pytest >= 90%, SAM lint
    steps_content = " ".join(
        step.get("run", "") + " " + step.get("name", "") for step in backend_job["steps"]
    )
    assert "ruff check" in steps_content
    assert "ruff format" in steps_content
    assert "scripts.export_openapi" in steps_content
    assert "git diff --exit-code ./frontend/src/types/api.ts" in steps_content
    assert "--cov-fail-under=90" in steps_content
    assert "template.yaml" in steps_content


def test_deploy_workflow_keyless_oidc_and_s3():
    """Validates CD deployment workflow keyless OIDC, caching headers, and health probe (REQ-CICD-001, REQ-CICD-002, REQ-CICD-014 to REQ-CICD-018)."""
    with open(_DEPLOY_FILE, encoding="utf-8") as f:
        raw_text = f.read()
        deploy_yaml = yaml.safe_load(raw_text)

    # 1. Keyless OIDC permissions (REQ-CICD-002)
    assert "permissions" in deploy_yaml
    assert deploy_yaml["permissions"].get("id-token") == "write"
    assert deploy_yaml["permissions"].get("contents") == "read"

    # 2. Strict absence of hardcoded AWS secrets (REQ-CICD-003)
    assert "AWS_ACCESS_KEY_ID:" not in raw_text
    assert "AWS_SECRET_ACCESS_KEY:" not in raw_text

    # 3. Role to assume uses GitHubActionsDeployerRole
    assert "GitHubActionsDeployerRole" in raw_text
    assert "us-east-2" in raw_text

    # 4. S3 Cache Headers (REQ-CICD-014, REQ-CICD-015)
    assert "max-age=31536000, immutable" in raw_text
    assert "max-age=0, must-revalidate" in raw_text

    # 5. CloudFront Cache Invalidation (REQ-CICD-016)
    assert "create-invalidation" in raw_text
    assert '"/index.html"' in raw_text

    # 6. Single post-deployment health check probe (REQ-CICD-017, REQ-CICD-018, REQ-SAM-026)
    assert "/api/health/ready" in raw_text
    # Ensure no recurring loop/crons (e.g. while sleep 10)
    assert "while true" not in raw_text
    assert "sleep 60" not in raw_text
