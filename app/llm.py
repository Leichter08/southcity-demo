import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

load_dotenv()


class LLMConfigurationError(RuntimeError):
    pass


def get_temperature(setting: str) -> float:
    value = os.getenv(setting)
    if value is None:
        raise LLMConfigurationError(f"{setting} is not configured.")
    try:
        return float(value)
    except ValueError as exc:
        raise LLMConfigurationError(f"{setting} must be a number.") from exc


def create_chat_model(temperature: float) -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER")
    model = os.getenv("LLM_MODEL")
    if not provider or not model:
        missing = [
            name
            for name, value in (("LLM_PROVIDER", provider), ("LLM_MODEL", model))
            if not value
        ]
        raise LLMConfigurationError(
            f"Missing language model settings: {', '.join(missing)}"
        )
    return init_chat_model(
        model,
        model_provider=provider,
        temperature=temperature,
    )
