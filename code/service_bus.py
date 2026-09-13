"""
service_bus.py
--------------
Inter-agent EVENTING (Lab 9-B). Agents do not call each other directly; they
publish events to Azure Service Bus and other agents/pods react. This decouples
the agents and lets you scale each one out independently.

Two backends behind one interface:
  AzureBus  -> real Azure Service Bus queue (set SERVICEBUS_CONNECTION_STRING)
  LocalBus  -> in-memory queue, so the lab runs offline with the SAME code path

Event types used in the demand-planner:
  forecast.created   : a run produced a forecast set
  forecast.flagged   : the verifier rejected a forecast (needs rework)
  forecast.approved  : the forecast passed and can be published
  rework.requested   : orchestrator asks a worker to redo its part
"""
import json
import os
from typing import Callable, List, Optional


class LocalBus:
    """In-memory bus for offline runs and tests. Same methods as AzureBus."""
    def __init__(self):
        self._queue: List[dict] = []

    def publish(self, event_type: str, payload: dict):
        self._queue.append({"type": event_type, "payload": payload})

    def receive(self, max_messages: int = 50) -> List[dict]:
        msgs, self._queue = self._queue[:max_messages], self._queue[max_messages:]
        return msgs

    def close(self):
        pass


class AzureBus:
    """Azure Service Bus queue backend."""
    def __init__(self, queue_name: str = "agent-events", conn: Optional[str] = None):
        from azure.servicebus import ServiceBusClient
        self._ServiceBusMessage = __import__("azure.servicebus", fromlist=["ServiceBusMessage"]).ServiceBusMessage
        conn = conn or os.environ["SERVICEBUS_CONNECTION_STRING"]
        self._client = ServiceBusClient.from_connection_string(conn)
        self._queue = queue_name

    def publish(self, event_type: str, payload: dict):
        body = json.dumps({"type": event_type, "payload": payload})
        with self._client.get_queue_sender(self._queue) as sender:
            sender.send_messages(self._ServiceBusMessage(body, subject=event_type))

    def receive(self, max_messages: int = 50) -> List[dict]:
        out = []
        with self._client.get_queue_receiver(self._queue, max_wait_time=5) as receiver:
            for msg in receiver.receive_messages(max_message_count=max_messages, max_wait_time=5):
                try:
                    out.append(json.loads(str(msg)))
                finally:
                    receiver.complete_message(msg)
        return out

    def close(self):
        self._client.close()


def get_bus(prefer_azure: bool = True):
    """Return AzureBus if configured, else LocalBus."""
    if prefer_azure and os.getenv("SERVICEBUS_CONNECTION_STRING"):
        try:
            bus = AzureBus(os.getenv("SERVICEBUS_QUEUE", "agent-events"))
            print("[bus] using Azure Service Bus.")
            return bus
        except Exception as e:  # noqa: BLE001
            print(f"[bus] Azure Service Bus unavailable ({type(e).__name__}); using LocalBus.")
    print("[bus] using in-memory LocalBus (offline).")
    return LocalBus()
