"""Shared in-memory RelayTransport fake used across tests."""

from __future__ import annotations

from typing import List, Optional


class FakeTransport:
    def __init__(self, fail_next: bool = False) -> None:
        self.masks_written: List[int] = []
        self.fail_next = fail_next
        self.all_off_calls = 0
        self.all_on_calls = 0

    def write_coil_mask(self, mask: int) -> None:
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError("simulated write failure")
        self.masks_written.append(mask)

    def read_back_state(self) -> Optional[int]:
        return self.masks_written[-1] if self.masks_written else None

    def all_coils_off(self) -> None:
        self.all_off_calls += 1

    def all_coils_on(self) -> None:
        self.all_on_calls += 1
