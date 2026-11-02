import asyncio
from typing import Optional, Set
from pydantic import BaseModel
from app.evidence.models import EntityType

class DiscoveryItem(BaseModel):
    entity_value: str
    entity_type: EntityType
    depth: int
    parent_entity: Optional[str] = None
    discovered_by: str

class DiscoveryQueue:
    """Manages breadth-first recursive investigation entities with cycle detection."""

    def __init__(self):
        self._queue = asyncio.Queue()
        self._visited: Set[str] = set()

    def push(self, item: DiscoveryItem) -> bool:
        signature = f"{item.entity_type.value}:{item.entity_value.strip().lower()}"
        if signature in self._visited:
            return False
        self._visited.add(signature)
        self._queue.put_nowait(item)
        return True

    async def pop(self) -> DiscoveryItem:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

    def size(self) -> int:
        return self._queue.qsize()

    def clear(self):
        self._visited.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break

