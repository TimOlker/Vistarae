# Copyright (c) 2026 Vistarae. All rights reserved.
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
