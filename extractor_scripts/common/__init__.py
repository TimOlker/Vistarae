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

"""Common infrastructure and base classes for Vistarae CLI extractors."""

from extractor_scripts.common.base import (
    BaseExtractor,
    extractor_options,
    print_summary,
    run_extractor_cli,
)
from extractor_scripts.common.exporter import CSVExporter
from extractor_scripts.common.geo import NominatimGeoClient
from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractionResult, ExtractorConfig

__all__ = [
    "BaseExtractor",
    "CSVExporter",
    "ExtractionResult",
    "ExtractorConfig",
    "NominatimGeoClient",
    "ResilientHttpClient",
    "extractor_options",
    "print_summary",
    "run_extractor_cli",
]
