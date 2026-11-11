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

"""Unit tests for BaseExtractor, Click options, and tag resolution pipeline."""

from pathlib import Path

from click.testing import CliRunner
from vistarae_core.schemas.extractor import ExtractorRecord

from extractor_scripts.common.base import (
    BaseExtractor,
    extractor_options,
    run_extractor_cli,
)
from extractor_scripts.common.models import ExtractorConfig


class DummyExtractor(BaseExtractor):
    """Dummy extractor implementation for testing base lifecycle and tagging."""

    name = "DummyExtractor"
    default_tags = ["BaselineTag"]

    def harvest_records(self) -> list[ExtractorRecord]:
        resolved_tags = self.resolve_tags(["ConditionalTag"])
        return [
            ExtractorRecord(
                poi_name="Dummy POI 1",
                country="United States",
                country_code="US",
                tags=resolved_tags,
            ),
            ExtractorRecord(
                poi_name="Dummy POI 2",
                country="United States",
                country_code="US",
                tags=resolved_tags,
            ),
        ]


@extractor_options(default_output="dummy.csv")
def dummy_cli(
    output_path: Path | None,
    limit: int | None,
    delay_seconds: float,
    deep: bool,
    cache_enabled: bool,
    split_size: int,
    geocode_missing: bool,
    user_tags: tuple[str, ...],
    dry_run: bool,
) -> None:
    """CLI entry point for DummyExtractor."""
    run_extractor_cli(
        extractor_cls=DummyExtractor,
        default_filename="dummy.csv",
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
        deep=deep,
        cache_enabled=cache_enabled,
        split_size=split_size,
        geocode_missing=geocode_missing,
        user_tags=user_tags,
        dry_run=dry_run,
    )


def test_tag_resolution_hierarchy() -> None:
    """Verifies baseline -> conditional -> user tags deduplication in correct order."""
    config = ExtractorConfig(
        output_path=Path("dummy.csv"),
        user_tags=["UserTag1", "BaselineTag", "CustomTag"],
    )
    extractor = DummyExtractor(config=config)
    tags = extractor.resolve_tags(["ConditionalTag", "UserTag1"])
    assert tags == ["BaselineTag", "ConditionalTag", "UserTag1", "CustomTag"]


def test_cli_help() -> None:
    """Verifies that --help displays all standardized options and exit code is 0."""
    runner = CliRunner()
    result = runner.invoke(dummy_cli, ["--help"])
    assert result.exit_code == 0
    assert "--output" in result.output
    assert "--limit" in result.output
    assert "--delay" in result.output
    assert "--deep" in result.output
    assert "--cache" in result.output
    assert "--split-size" in result.output
    assert "--geocode" in result.output
    assert "--tag" in result.output
    assert "--dry-run" in result.output


def test_cli_dry_run_no_files_written(tmp_path: Path) -> None:
    """Verifies --dry-run prints terminal summary without creating CSV on disk."""
    runner = CliRunner()
    out_file = tmp_path / "dummy_out.csv"
    result = runner.invoke(dummy_cli, ["--output", str(out_file), "--dry-run", "--tag", "CLITag"])
    assert result.exit_code == 0
    assert "Vistarae Extractor Summary: DummyExtractor (DRY RUN)" in result.output
    assert "Total Records Harvested: 2" in result.output
    assert not out_file.exists()


def test_cli_execution_with_export(tmp_path: Path) -> None:
    """Verifies actual execution writing CSV file to disk."""
    runner = CliRunner()
    out_file = tmp_path / "dummy_out.csv"
    result = runner.invoke(
        dummy_cli,
        ["--output", str(out_file), "--limit", "1", "-t", "OperatorTag"],
    )
    assert result.exit_code == 0
    assert "Output Files Generated:" in result.output
    assert out_file.exists()

    content = out_file.read_text(encoding="utf-8-sig")
    assert "Dummy POI 1" in content
    assert "Dummy POI 2" not in content
    assert "BaselineTag; ConditionalTag; OperatorTag" in content


def test_cli_invalid_parameter_exit_code_2() -> None:
    """Verifies exit code 2 when an invalid option or out-of-range value is supplied."""
    runner = CliRunner()
    result = runner.invoke(dummy_cli, ["--limit", "0"])
    assert result.exit_code == 2
    assert "Invalid value for '-l' / '--limit'" in result.output


def test_extractor_lifecycle_with_geocode(monkeypatch) -> None:
    """Verifies that geocode client is initialized and closed when geocode_missing is True."""
    config = ExtractorConfig(
        output_path=Path("dummy.csv"),
        geocode_missing=True,
    )
    extractor = DummyExtractor(config=config)
    assert extractor.geo is not None
    extractor.close()


def test_cli_execution_failure_exit_code_1(monkeypatch) -> None:
    """Verifies exit code 1 when extraction raises an exception."""

    class FailingExtractor(BaseExtractor):
        name = "Failing"

        def harvest_records(self) -> list[ExtractorRecord]:
            raise RuntimeError("Scraping failure simulated")

    @extractor_options(default_output="fail.csv")
    def failing_cli(**kwargs):
        run_extractor_cli(
            extractor_cls=FailingExtractor,
            default_filename="fail.csv",
            **kwargs,
        )

    runner = CliRunner()
    result = runner.invoke(failing_cli, [])
    assert result.exit_code == 1
    assert "Error during extraction: Scraping failure simulated" in result.output
