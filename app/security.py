import logging

from app.llm import create_chat_model
from app.prompts import PROMPT_INJECTION_GUARD_PROMPT

logger = logging.getLogger(__name__)


class GuardrailError(RuntimeError):
    pass


async def evaluate_injection_with_llm(user_input: str) -> bool:
    try:
        response = await create_chat_model(temperature=0.0).ainvoke(
            [
                ("system", PROMPT_INJECTION_GUARD_PROMPT),
                ("human", user_input),
            ]
        )
    except Exception as exc:
        logger.exception("Prompt injection guard evaluation failed")
        raise GuardrailError("Prompt injection guard evaluation failed.") from exc

    content = getattr(response, "content", None)
    if not isinstance(content, str):
        logger.error("Prompt injection guard returned a non-text response")
        raise GuardrailError("Prompt injection guard returned an invalid response.")

    result = content.strip().upper()
    if result == "SAFE":
        return False
    if result == "INJECTION":
        return True

    logger.error("Prompt injection guard returned an unrecognized label")
    raise GuardrailError("Prompt injection guard returned an invalid response.")
