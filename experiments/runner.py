import random

from django.utils import timezone

from agents.models import Agent
from simulation.engine import SimulationEngine
from simulation.models import Resource, World

from .models import Experiment, ExperimentResult


class ExperimentRunner:

    def __init__(self, experiment):
        self.experiment = experiment

    def setup(self):

        config = self.experiment.configuration

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
            )

            for tick in range(self.experiment.total_ticks):
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

        total_wallet = sum(
            agent["wallet"]
            for agent in final_agents
        )

        metrics = {
            "agent_count": len(final_agents),
            "total_wallet": total_wallet,
            "resource_count": len(final_resources),
        }

        return ExperimentResult.objects.create(
            experiment=self.experiment,
            final_world_state=final_world,
            final_agent_states=final_agents,
            metrics=metrics,
        )
