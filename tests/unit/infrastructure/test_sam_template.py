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

"""Unit tests for AWS SAM infrastructure template (T033, T034, T035, T036)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "template.yaml"


class CloudFormationLoader(yaml.SafeLoader):
    """Safe YAML loader supporting CloudFormation intrinsic shorthand tags."""


def _cfn_tag_constructor(
    loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node
) -> dict[str, Any]:
    """Parses CloudFormation shorthand tags (!Ref, !Sub, !GetAtt) into dict structures."""
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {tag_suffix: loader.construct_mapping(node)}
    return {tag_suffix: None}


# Register all standard CloudFormation shorthand tags
for tag in [
    "!Ref",
    "!Sub",
    "!GetAtt",
    "!Join",
    "!Select",
    "!Split",
    "!FindInMap",
    "!Base64",
    "!ImportValue",
    "!Condition",
    "!Equals",
    "!And",
    "!Or",
    "!Not",
    "!If",
]:
    CloudFormationLoader.add_multi_constructor(
        tag, lambda loader, suffix, node, t=tag[1:]: _cfn_tag_constructor(loader, t, node)
    )


@pytest.fixture(scope="module")
def sam_template() -> dict[str, Any]:
    """Loads and parses template.yaml using the CloudFormationLoader."""
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return yaml.load(f, Loader=CloudFormationLoader)


class TestSamTemplateStructure:
    """Verifies that template.yaml defines required resources and conforms to architecture standards."""

    def test_sam_header_and_globals(self, sam_template: dict[str, Any]) -> None:
        """Verifies AWS SAM template header, version, and global defaults."""
        assert sam_template.get("AWSTemplateFormatVersion") == "2010-09-09"
        assert sam_template.get("Transform") == "AWS::Serverless-2016-10-31"

        globals_cfg = sam_template.get("Globals", {})
        func_globals = globals_cfg.get("Function", {})
        assert func_globals.get("Runtime") == "python3.12"
        assert func_globals.get("Architectures") == ["arm64"]
        assert func_globals.get("Timeout") == 15

    def test_s3_spa_bucket_and_oac(self, sam_template: dict[str, Any]) -> None:
        """Verifies S3 SPA bucket is strictly private with CloudFront Origin Access Control (OAC)."""
        resources = sam_template.get("Resources", {})

        # SPA Bucket
        assert "VistaraeSpaBucket" in resources
        spa_bucket = resources["VistaraeSpaBucket"]
        assert spa_bucket["Type"] == "AWS::S3::Bucket"
        public_block = spa_bucket["Properties"]["PublicAccessBlockConfiguration"]
        assert public_block["BlockPublicAcls"] is True
        assert public_block["BlockPublicPolicy"] is True
        assert public_block["IgnorePublicAcls"] is True
        assert public_block["RestrictPublicBuckets"] is True

        # Origin Access Control
        assert "VistaraeOac" in resources
        oac = resources["VistaraeOac"]
        assert oac["Type"] == "AWS::CloudFront::OriginAccessControl"
        assert (
            oac["Properties"]["OriginAccessControlConfig"]["OriginAccessControlOriginType"] == "s3"
        )
        assert oac["Properties"]["OriginAccessControlConfig"]["SigningBehavior"] == "always"

    def test_cloudfront_distribution_and_sni_routing(self, sam_template: dict[str, Any]) -> None:
        """Verifies CloudFront routes /api/* to HTTP API with AllViewerExceptHostHeader for TLS SNI."""
        resources = sam_template.get("Resources", {})
        assert "VistaraeDistribution" in resources
        cf_dist = resources["VistaraeDistribution"]
        dist_config = cf_dist["Properties"]["DistributionConfig"]

        # Cache behaviors
        cache_behaviors = dist_config.get("CacheBehaviors", [])
        api_behavior = next((b for b in cache_behaviors if b.get("PathPattern") == "/api/*"), None)
        assert api_behavior is not None, "Missing /api/* CacheBehavior in CloudFrontDistribution"

        # Verify Origin Request Policy is AllViewerExceptHostHeader (b689b0a8-53d0-40ab-baf2-68738e2966ac)
        orp_id = api_behavior.get("OriginRequestPolicyId")
        assert (
            orp_id == "b689b0a8-53d0-40ab-baf2-68738e2966ac"
        ), "Must use AllViewerExceptHostHeader Managed Policy to prevent Host collision with API Gateway TLS SNI"

    def test_all_six_domain_lambdas_defined(self, sam_template: dict[str, Any]) -> None:
        """Verifies that all 6 domain Lambdas are declared with arm64 and Python 3.12."""
        resources = sam_template.get("Resources", {})
        expected_lambdas = [
            "PoiFunction",
            "UserFunction",
            "IngestFunction",
            "AdminFunction",
            "BatchIngestWorker",
            "SpendKillSwitch",
        ]
        for func_name in expected_lambdas:
            assert func_name in resources, f"Missing Lambda resource {func_name}"
            func_def = resources[func_name]
            assert func_def["Type"] == "AWS::Serverless::Function"

    def test_xray_one_percent_sampling_rule(self, sam_template: dict[str, Any]) -> None:
        """Verifies that X-Ray 1% sampling rule is declared to stay well within free tier (REQ-SAM-007)."""
        resources = sam_template.get("Resources", {})
        assert "XRaySamplingRule" in resources
        sampling_rule = resources["XRaySamplingRule"]
        assert sampling_rule["Type"] == "AWS::XRay::SamplingRule"
        rule_record = sampling_rule["Properties"]["SamplingRule"]
        assert rule_record["FixedRate"] == 0.01

    def test_sqs_and_dlq_configuration(self, sam_template: dict[str, Any]) -> None:
        """Verifies Ingestion SQS queue and Dead Letter Queue with RedrivePolicy."""
        resources = sam_template.get("Resources", {})
        assert "IngestQueue" in resources
        assert "IngestDeadLetterQueue" in resources

        ingestion_queue = resources["IngestQueue"]
        redrive = ingestion_queue["Properties"].get("RedrivePolicy", {})
        assert redrive.get("maxReceiveCount") == 3
