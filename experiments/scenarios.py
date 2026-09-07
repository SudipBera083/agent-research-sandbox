def scenario_definitions():
    agents = [
        {
            "name": "Agent 1",
            "role": "wealth",
            "wallet": 100,
            "goals": ["Maximize wealth"],
        },
        {
            "name": "Agent 2",
            "role": "survival",
            "wallet": 100,
            "goals": ["Maintain food reserves"],
        },
        {
            "name": "Agent 3",
            "role": "cooperative",
            "wallet": 100,
            "inventory": {"food": 2},
            "goals": ["Cooperate with other agents"],
        },
    ]

    def build(name, seed, quantity, price=10):
        return {
            "name": name,
            "seed": seed,
            "configuration": {
                "world": {
                    "name": f"{name} World",
                    "resources": [
                        {
                            "name": "food",
                            "price": price,
                            "quantity": quantity,
                        }
                    ],
                },
                "memory": {
                    "enabled": True,
                    "top_k": 10,
                    "decay": 0.95,
                },
                "simulation": {"ticks": 10},
                "agents": agents,
            },
        }

    return {
        "baseline": build("baseline", 101, 100),
        "resource_scarcity": build("resource_scarcity", 102, 12),
        "abundant_resources": build("abundant_resources", 103, 1000),
        "trade_opportunity": build("trade_opportunity", 104, 100),
        "communication_pressure": build(
            "communication_pressure",
            105,
            25,
            price=12,
        ),
    }