from django.db import transaction

from .models import Trade


class TradeEngine:

    @staticmethod
    @transaction.atomic
    def execute(trade):

        if trade.status != "accepted":
            return {
                "success": False,
                "error": "Trade must be accepted first.",
            }

        proposer = trade.proposer
        recipient = trade.recipient
        offer = trade.offer

        give = offer.get("give", {})
        receive = offer.get("receive", {})

        give_resource = give.get("resource")
        give_quantity = give.get("quantity", 0)

        receive_resource = receive.get("resource")
        receive_quantity = receive.get("quantity", 0)

        if give_quantity <= 0 or receive_quantity <= 0:
            trade.status = "failed"
            trade.save(update_fields=["status", "updated_at"])

            return {
                "success": False,
                "error": "Trade quantities must be positive.",
            }

        if give_resource == "money":

            if proposer.wallet < give_quantity:
                trade.status = "failed"
                trade.save(update_fields=["status", "updated_at"])

                return {
                    "success": False,
                    "error": "Proposer has insufficient money.",
                }

        else:

            inventory = proposer.inventory or {}

            if inventory.get(give_resource, 0) < give_quantity:
                trade.status = "failed"
                trade.save(update_fields=["status", "updated_at"])

                return {
                    "success": False,
                    "error": "Proposer has insufficient resources.",
                }

        if receive_resource == "money":

            if recipient.wallet < receive_quantity:
                trade.status = "failed"
                trade.save(update_fields=["status", "updated_at"])

                return {
                    "success": False,
                    "error": "Recipient has insufficient money.",
                }

        else:

            inventory = recipient.inventory or {}

            if inventory.get(receive_resource, 0) < receive_quantity:
                trade.status = "failed"
                trade.save(update_fields=["status", "updated_at"])

                return {
                    "success": False,
                    "error": "Recipient has insufficient resources.",
                }

        if give_resource == "money":
            proposer.wallet -= give_quantity
            recipient.wallet += give_quantity

        else:
            proposer_inventory = proposer.inventory or {}
            recipient_inventory = recipient.inventory or {}
            proposer_inventory[give_resource] -= give_quantity
            recipient_inventory[give_resource] = (
                recipient_inventory.get(give_resource, 0)
                + give_quantity
            )
            proposer.inventory = proposer_inventory
            recipient.inventory = recipient_inventory

        if receive_resource == "money":
            recipient.wallet -= receive_quantity
            proposer.wallet += receive_quantity

        else:
            recipient_inventory = recipient.inventory or {}
            proposer_inventory = proposer.inventory or {}
            recipient_inventory[receive_resource] -= receive_quantity
            proposer_inventory[receive_resource] = (
                proposer_inventory.get(receive_resource, 0)
                + receive_quantity
            )
            recipient.inventory = recipient_inventory
            proposer.inventory = proposer_inventory

        proposer.save()
        recipient.save()

        trade.status = "completed"
        trade.save(update_fields=["status", "updated_at"])

        return {
            "success": True,
            "trade_id": trade.id,
            "proposer": proposer.name,
            "recipient": recipient.name,
            "offer": offer,
        }
