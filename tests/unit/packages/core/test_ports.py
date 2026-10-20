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

"""Unit tests for Protocol port definitions (T-008).

Verifies typing.Protocol interfaces for repositories, identity, and queues.
"""

from __future__ import annotations

import typing

from vistarae_core.ports.identity import IIdentityProvider
from vistarae_core.ports.queue import IMessageQueue
from vistarae_core.ports.repositories import (
    IIdempotencyRepository,
    IQuotaRepository,
    IUserRepository,
)


def test_ports_are_protocols() -> None:
    """Asserts that all port interfaces are typing.Protocol classes."""
    assert issubclass(IIdentityProvider, typing.Protocol)
    assert issubclass(IMessageQueue, typing.Protocol)
    assert issubclass(IUserRepository, typing.Protocol)
    assert issubclass(IQuotaRepository, typing.Protocol)
    assert issubclass(IIdempotencyRepository, typing.Protocol)
