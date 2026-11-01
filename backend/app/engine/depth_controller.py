from app.config import settings

class DepthController:
    """Enforces investigation depth limits, entity bounds, and recursion throttling."""

    def __init__(self, max_depth: int = None, max_entities: int = None):
        self.max_depth = max_depth or settings.limits.max_depth
        self.max_entities = max_entities or settings.limits.max_discovered_entities
        self.current_entity_count = 0

    def can_expand(self, current_depth: int) -> bool:
        if current_depth >= self.max_depth:
            return False
        if self.current_entity_count >= self.max_entities:
            return False
        return True

    def register_entity(self) -> bool:
        if self.current_entity_count >= self.max_entities:
            return False
        self.current_entity_count += 1
        return True

    def reset(self):
        self.current_entity_count = 0
