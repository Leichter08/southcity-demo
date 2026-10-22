import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.security import GuardrailError, evaluate_injection_with_llm


class PromptInjectionGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_false_for_safe_response(self) -> None:
        await self.assert_guard_result(" SAFE ", expected=False)

    async def test_returns_true_for_injection_response(self) -> None:
        await self.assert_guard_result(" injection ", expected=True)

    async def test_rejects_unrecognized_response(self) -> None:
        with patch(
            "app.security.create_chat_model",
            return_value=_FakeChatModel("maybe"),
        ):
            with self.assertRaises(GuardrailError):
                await evaluate_injection_with_llm("question")

    async def test_rejects_non_text_response(self) -> None:
        with patch(
            "app.security.create_chat_model",
            return_value=_FakeChatModel(None),
        ):
            with self.assertRaises(GuardrailError):
                await evaluate_injection_with_llm("question")

    async def test_wraps_model_failure(self) -> None:
        with patch(
            "app.security.create_chat_model",
            return_value=_FakeChatModel(error=RuntimeError("model unavailable")),
        ):
            with self.assertRaises(GuardrailError):
                await evaluate_injection_with_llm("question")

    async def assert_guard_result(self, content: str, expected: bool) -> None:
        with patch(
            "app.security.create_chat_model",
            return_value=_FakeChatModel(content),
        ) as create_chat_model:
            result = await evaluate_injection_with_llm("question")

        self.assertIs(result, expected)
        create_chat_model.assert_called_once_with(temperature=0.0)


class _FakeChatModel:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error

    async def ainvoke(self, messages: list[tuple[str, str]]) -> SimpleNamespace:
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=self.content)
