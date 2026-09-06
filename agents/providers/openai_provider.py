import json

from django.conf import settings
from openai import OpenAI

from .base import LLMProvider, LLMResponse


ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "buy",
                "sell",
                "communicate",
                "propose_trade",
                "accept_trade",
                "reject_trade",
                "wait",
            ],
        },
        "parameters": {
            "type": "object",
            "additionalProperties": True,
        },
    },
    "required": ["action", "parameters"],
}


class XAIProvider(LLMProvider):

    provider_name = "xai"
    prompt_version = "agent-action-v1"
    input_cost_per_million = 1.25
    output_cost_per_million = 2.50

    def __init__(self, api_key=None, model=None, timeout=None):
        self.model_name = model or settings.XAI_MODEL
        self.api_key = api_key or settings.XAI_API_KEY

        self.timeout = timeout or settings.XAI_TIMEOUT_SECONDS
        self.client = None

    def generate(self, messages):
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY is not configured.")

        if self.client is None:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.x.ai/v1",
                timeout=self.timeout,
            )

        system_message = {
            "role": "system",
            "content": (
                "You are a constrained research agent. "
                "Return only the requested JSON action. "
                "Never describe Python, tools, databases, or world mutation."
            ),
        }

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[system_message, *messages],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_action",
                    "strict": True,
                    "schema": ACTION_SCHEMA,
                },
            },
        )

        message = response.choices[0].message
        content = message.content or ""
        usage = {}

        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            raw_response=json.dumps(
                response.model_dump(),
                default=str,
            ),
            usage=usage,
        )
