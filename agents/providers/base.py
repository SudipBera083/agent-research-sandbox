from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    content: str
    raw_response: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider:

    provider_name = "base"
    model_name = "base"
    prompt_version = "agent-action-v1"
    input_cost_per_million = 0.0
    output_cost_per_million = 0.0

    def generate(self, messages):
        raise NotImplementedError
