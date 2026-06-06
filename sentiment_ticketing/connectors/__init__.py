from .base import TicketConnector

__all__ = ["FreshdeskConnector", "GenericHttpConnector", "TicketConnector"]


def __getattr__(name: str):
    if name == "FreshdeskConnector":
        from .freshdesk import FreshdeskConnector

        return FreshdeskConnector
    if name == "GenericHttpConnector":
        from .generic_http import GenericHttpConnector

        return GenericHttpConnector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
