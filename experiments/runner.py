import random

from django.utils import timezone

from agents.models import Agent
from simulation.engine import SimulationEngine
from simulation.models import Resource, World

from .metrics import ExperimentMetrics
from .models import Experiment, ExperimentResult


class ExperimentRunner:

    def __init__(self, experiment):
        self.experiment = experiment
        self.config = self._normalize_configuration(
            experiment.configuration
        )

    def _normalize_configuration(self, configuration):
        world = configuration.get("world", {})
        memory = configuration.get("memory", {})
        simulation = configuration.get("simulation", {})

        return {
            "world_name": world.get(
                "name",
                configuration.get(
                    "world_name",
                    self.experiment.name,
                ),
            ),
            "world_description": world.get(
                "description",
                configuration.get("world_description", ""),
            ),
            "resources": world.get(
                "resources",
                configuration.get("resources", []),
            ),
            "agents": configuration.get("agents", []),
            "memory_enabled": memory.get(
                "enabled",
                configuration.get("memory_enabled", True),
            ),
            "memory_top_k": memory.get(
                "top_k",
                configuration.get("memory_top_k", 10),
            ),
            "memory_decay": memory.get(
                "decay",
                configuration.get("memory_decay", 0.95),
            ),
            "total_ticks": simulation.get(
                "ticks",
                self.experiment.total_ticks,
            ),
        }

    def setup(self):

        config = self.config

        if self.experiment.seed is not None:
            random.seed(self.experiment.seed)

        world = World.objects.create(
            name=config.get(
                "world_name",
                self.experiment.name,
            ),
            description=config.get(
                "world_description",
                "",
            ),
            current_tick=0,
        )

        resources = config.get("resources", [])

        for resource in resources:
            Resource.objects.create(
                world=world,
                name=resource["name"],
                price=resource["price"],
                quantity=resource["quantity"],
            )

        agents = []

        for agent_config in config.get("agents", []):
            agent = Agent.objects.create(
                name=agent_config["name"],
                role=agent_config.get(
                    "role",
                    "general",
                ),
                runtime_type=agent_config.get(
                    "runtime_type",
                    agent_config.get("runtime", "rule"),
                ),
                provider=agent_config.get(
                    "provider",
                    "",
                ),
                model=agent_config.get(
                    "model",
                    "",
                ),
                world=world,
                system_prompt=agent_config.get(
                    "system_prompt",
                    "",
                ),
                goals=agent_config.get(
                    "goals",
                    [],
                ),
                personality=agent_config.get(
                    "personality",
                    {},
                ),
                wallet=agent_config.get(
                    "wallet",
                    100.0,
                ),
                inventory=agent_config.get(
                    "inventory",
                    {},
                ),
            )

            agents.append(agent)

        return world, agents

    def run(self):

        self.experiment.status = "running"
        self.experiment.started_at = timezone.now()
        self.experiment.save()

        try:
            world, agents = self.setup()
            engine = SimulationEngine(
                world,
                experiment=self.experiment,
                memory_policy={
                    "memory_enabled": self.config["memory_enabled"],
                    "memory_top_k": self.config["memory_top_k"],
                    "memory_decay": self.config["memory_decay"],
                },
            )

            for tick in range(self.config["total_ticks"]):
                world.current_tick = tick + 1
                world.save()

                self.experiment.current_tick = tick + 1
                self.experiment.save()

                for agent in agents:
                    agent.refresh_from_db()

                    if not agent.is_active:
                        continue

                    engine.run_agent(agent)

            result = self.create_result(
                world,
                agents,
            )

            self.experiment.status = "completed"
            self.experiment.completed_at = timezone.now()
            self.experiment.save()

            return result

        except Exception:
            self.experiment.status = "failed"
            self.experiment.save()
            raise

    def create_result(self, world, agents):

        final_agents = []

        for agent in agents:
            agent.refresh_from_db()

            final_agents.append({
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "wallet": agent.wallet,
                "inventory": agent.inventory,
                "goals": agent.goals,
            })

        final_resources = [
            {
                "name": resource.name,
                "price": resource.price,
                "quantity": resource.quantity,
            }
            for resource in world.resources.all()
        ]

        final_world = {
            "name": world.name,
            "tick": world.current_tick,
            "resources": final_resources,
        }

        metrics = ExperimentMetrics(
            self.experiment,
            world,
            agents,
        ).calculate()

        return ExperimentResult.objects.create(
            experiment=self.experiment,
            final_world_state=final_world,
            final_agent_states=final_agents,
            metrics=metrics,
        )
