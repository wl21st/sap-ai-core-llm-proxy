"""Protocol definitions for converter implementations."""

from typing import Any, Protocol


class Converter(Protocol):
    """Interface for converter implementations."""

    @staticmethod
    def convert(payload: dict[str, Any]) -> dict[str, Any]:
        """Convert payload into target format."""
