from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from miscutils import ReprMixin
from subtypes import Dict, Str, NameSpace

from .registry import Registry
from .mapper import LabelMapper


if TYPE_CHECKING:
    from gmailapi.gmail import Gmail


class Root(ReprMixin):
    def __init__(self, gmail: Gmail) -> None:
        self.gmail = gmail
        self.children: dict[str, Node] = {}

    def refresh(self, old_registry: Registry, new_registry: Registry, root_namespace: NameSpace) -> None:

        self.register_children_recursively(labels=Dict(self.gmail.service.users().labels().list(userId="me").execute()).labels,
                                           old_registry=old_registry, new_registry=new_registry)
        self.regenerate_labels(root_namespace=root_namespace)

    def register_children_recursively(self, labels: list, old_registry: Registry, new_registry: Registry) -> None:
        from .accessor import LabelAccessor

        children, deep_children = [], []

        for label in labels:
            if "/" in label.name:
                deep_children.append(label)
            else:
                if label.id not in LabelAccessor._system_ids:
                    children.append(label)

        for child in children:
            if old_registry.contains_by_id(child.id):
                node = old_registry.get_by_id(child.id)
                node.parent = None
            else:
                node = Node(gmail=self.gmail, id_=child.id, name=child.name, parent=None)

            self.children[child.name] = node

        for child in self.children.values():
            child.register_children_recursively(deep_children, old_registry=old_registry, new_registry=new_registry)

    def regenerate_labels(self, root_namespace: NameSpace) -> None:
        root_namespace({name: child.proxy for name, child in self.children.items()})

        for child in self.children.values():
            child.regenerate_labels()


class Node(LabelMapper):
    def __init__(self, gmail: Gmail, id_: str, name: str, parent: Optional[Node]) -> None:
        super().__init__(gmail=gmail, id_=id_, name=name)
        self.parent = parent
        self.children: dict[str, Node] = {}

    def register_children_recursively(self, labels: list, old_registry: Registry, new_registry: Registry) -> None:
        new_registry.set(self)

        children = [label for label in labels if label.name.startswith(self.name)]
        deep_children = []

        for label in labels:
            if "/" in (name := Str(label.name).slice.after_first(f"{self.name}/")):
                deep_children.append(label)
            else:
                if old_registry.contains_by_id(label.id):
                    node = old_registry.get_by_id(label.id)
                    node.parent = self
                else:
                    node = type(self)(gmail=self.gmail, id_=label.id, name=label.name, parent=self)

                self.children[name] = node

        for child in self.children.values():
            child.register_children_recursively(deep_children, old_registry=old_registry, new_registry=new_registry)

    def regenerate_labels(self) -> None:
        self.proxy({name: child.proxy for name, child in self.children.items()})

        for child in self.children.values():
            child.regenerate_labels()
