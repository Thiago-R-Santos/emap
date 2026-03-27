from abc import ABC, abstractmethod
from arbitrage.models import Event


class BaseCollector(ABC):
    """Interface base para coletores de odds."""

    @abstractmethod
    async def fetch_events(self) -> list[Event]:
        """Busca todos os eventos com odds disponíveis."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Nome identificador do coletor."""
        ...
