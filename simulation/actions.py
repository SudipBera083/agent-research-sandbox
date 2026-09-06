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
    PROPOSE_TRADE = "propose_trade"
    ACCEPT_TRADE = "accept_trade"
    REJECT_TRADE = "reject_trade"
    WAIT = "wait"