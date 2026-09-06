from django.core.management.base import BaseCommand

from agents.models import Agent
from simulation.models import Conversation, Trade
from simulation.trading import TradeEngine


class Command(BaseCommand):

    help = "Run an isolated trade-engine test"

    def handle(self, *args, **options):

        agent_a = Agent.objects.order_by("id").first()
        agent_b = Agent.objects.order_by("id")[1]

        conversation = Conversation.objects.create(
            conversation_id=f"test-trade-{agent_a.id}-{agent_b.id}",
            topic="trade",
        )

        conversation.participants.add(
            agent_a,
            agent_b,
        )

        trade = Trade.objects.create(
            conversation=conversation,
            proposer=agent_a,
            recipient=agent_b,
            offer={
                "give": {
                    "resource": "food",
                    "quantity": 2,
                },
                "receive": {
                    "resource": "money",
                    "quantity": 20,
                },
            },
            status="accepted",
        )

        result = TradeEngine.execute(trade)

        self.stdout.write(
            self.style.SUCCESS(
                f"Trade result: {result}"
            )
        )

        agent_a.refresh_from_db()
        agent_b.refresh_from_db()

        self.stdout.write(
            f"{agent_a.name}: wallet={agent_a.wallet}, "
            f"inventory={agent_a.inventory}"
        )

        self.stdout.write(
            f"{agent_b.name}: wallet={agent_b.wallet}, "
            f"inventory={agent_b.inventory}"
        )
