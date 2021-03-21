from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mapper import BaseMapper


class Registry:
    def __init__(self):
        self.id_mappings: dict[str, BaseMapper] = {}
        self.name_mappings: dict[str, BaseMapper] = {}

    def get_by_id(self, id_: str) -> BaseMapper:
        return self.id_mappings[id_]

    def get_by_name(self, name: str) -> BaseMapper:
        return self.name_mappings[name]

    def set(self, node: BaseMapper) -> None:
        self.id_mappings[node.id] = node
        self.name_mappings[node.name] = node

    def pop_by_id(self, id_: str):
        self.name_mappings.pop(self.id_mappings.pop(id_).name)

    def pop_by_name(self, name: str):
        self.id_mappings.pop(self.name_mappings.pop(name).id)

    def pop(self, node: BaseMapper):
        self.id_mappings.pop(node.id)
        self.name_mappings.pop(node.name)

    def contains_by_id(self, id_: str) -> bool:
        return id_ in self.id_mappings

    def contains_by_name(self, name: str) -> bool:
        return name in self.name_mappings

    def clear(self) -> None:
        self.id_mappings.clear()
        self.name_mappings.clear()
