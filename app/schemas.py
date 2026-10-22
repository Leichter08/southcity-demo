from typing import Literal

from pydantic import BaseModel, Field, field_validator

UserRole = Literal["Sales_Staff", "Management"]


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        prompt = value.strip()
        if not prompt:
            raise ValueError("Prompt cannot be blank")
        return prompt


class PromptResponse(BaseModel):
    answer: str
