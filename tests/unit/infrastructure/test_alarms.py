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

"""Unit tests for CloudWatch alarms, free-tier limits, and zero recurring pings (T038)."""

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


for tag in ["!Ref", "!Sub", "!GetAtt", "!Join", "!Select", "!Split"]:
    CloudFormationLoader.add_multi_constructor(
        tag, lambda loader, suffix, node, t=tag[1:]: _cfn_tag_constructor(loader, t, node)
    )


@pytest.fixture(scope="module")
def sam_template() -> dict[str, Any]:
    """Loads and parses template.yaml using the CloudFormationLoader."""
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return yaml.load(f, Loader=CloudFormationLoader)


class TestCloudWatchAlarmsAndLimits:
    """Verifies that alarms stay strictly within free-tier budget and permit Neon compute scale-to-zero."""

    def test_alarm_count_strictly_under_free_tier_ceiling(
        self, sam_template: dict[str, Any]
    ) -> None:
        """Total CloudWatch alarm count must be <= 2 (strictly under the 10 free-tier ceiling)."""
        resources = sam_template.get("Resources", {})
        alarm_resources = [
            res_id
            for res_id, res_def in resources.items()
            if res_def.get("Type") == "AWS::CloudWatch::Alarm"
        ]

        # Must not exceed 2 alarms (ApplicationErrorAlarm and DlqMessageAlarm)
        assert len(alarm_resources) <= 2, (
            f"Too many alarms defined: {alarm_resources}. Max allowed is 2 (<10)."
        )
        assert "ApplicationErrorAlarm" in alarm_resources
        assert "DlqMessageAlarm" in alarm_resources

    def test_zero_recurring_synthetic_health_pings(self, sam_template: dict[str, Any]) -> None:
        """Ensures NO recurring EventBridge schedules or Synthetics canaries keep Neon compute awake."""
        resources = sam_template.get("Resources", {})

        for res_id, res_def in resources.items():
            res_type = res_def.get("Type", "")

            # No CloudWatch Synthetics canaries
            assert res_type != "AWS::Synthetics::Canary", (
                f"Resource {res_id} is a Canary. Scheduled pings prevent Neon scale-to-zero!"
            )

            # No Route 53 health check
            assert res_type != "AWS::Route53::HealthCheck", (
                f"Resource {res_id} is a Route53 HealthCheck. Pings prevent Neon scale-to-zero!"
            )

            # If EventBridge rule, verify it is NOT a recurring schedule
            if res_type == "AWS::Events::Rule":
                props = res_def.get("Properties", {})
                assert "ScheduleExpression" not in props, (
                    f"Resource {res_id} has a recurring schedule: {props.get('ScheduleExpression')}. "
                    "Must not schedule recurring pings."
                )
