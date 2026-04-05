"""Unit tests for utility helpers."""

from orchestrator.utils import add


class TestAdd:
    def test_adds_integers(self) -> None:
        assert add(2, 3) == 5

    def test_adds_floats(self) -> None:
        assert add(2.5, 3.5) == 6.0

    def test_adds_mixed_numeric_types(self) -> None:
        assert add(2, 3.5) == 5.5
