import json

from django.conf import settings
from openai import OpenAI

from .base import LLMProvider, LLMResponse


class GroqProvider(LLMProvider):

    provider_name = "groq"
    prompt_version = "agent-action-v1"
    input_cost_per_million = 0.0
    output_cost_per_million = 0.0

    def __init__(self, model=None):
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        self.model_name = model or settings.GROQ_MODEL
        self.client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            timeout=settings.GROQ_TIMEOUT_SECONDS,
        )

    def generate(self, messages):
        system_message = {
            "role": "system",
            "content": (
                "You are an autonomous agent operating inside a research "
                "sandbox. Return exactly one valid JSON object. The JSON "
                "object must contain an 'action' field and a 'parameters' "
                "field. Do not return markdown, explanations, or additional "
                "text."
            ),
        }

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[system_message, *messages],
            response_format={
                "type": "json_object",
            },
        )
        usage = {}

        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=response.choices[0].message.content or "",
            raw_response=json.dumps(
                response.model_dump(),
                default=str,
            ),
            usage=usage,
        )
