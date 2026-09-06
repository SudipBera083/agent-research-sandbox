from dataclasses import dataclass
from typing import Any


@dataclass
class Action:
    agent_id: int
    action_type: str
    parameters: dict[str, Any]


class ActionTypes:
    OBSERVE = "observe"
    BUY = "buy"
    SELL = "sell"
    COMMUNICATE = "communicate"
    WAIT = "wait"