"""Tests for core/executor/base.py."""

from orchestrator.core.executor.base import AgentExecutor


def test_agent_executor_is_abstract():
    """AgentExecutor cannot be instantiated directly."""
    import pytest

    with pytest.raises(TypeError):
        AgentExecutor()  # type: ignore[abstract]


def test_agent_executor_subclass():
    """Subclass can set executor_type."""
    from orchestrator.core.models.schemas import AgentResult

    class MockExecutor(AgentExecutor):
        executor_type = "mock"

        async def run(self, prompt, *, timeout=300, context=None):  # noqa: ASYNC109
            return AgentResult(output=prompt)

        async def health_check(self):
            return True

    executor = MockExecutor()
    assert executor.executor_type == "mock"


async def test_mock_executor_run():
    from orchestrator.core.models.schemas import AgentResult

    class MockExecutor(AgentExecutor):
        executor_type = "mock"

        async def run(self, prompt, *, timeout=300, context=None):  # noqa: ASYNC109
            return AgentResult(output=f"echo: {prompt}")

        async def health_check(self):
            return True

    executor = MockExecutor()
    result = await executor.run("test prompt")
    assert result.output == "echo: test prompt"
