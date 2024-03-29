from __future__ import annotations

from typing import Union, TYPE_CHECKING

from subtypes import Dict

if TYPE_CHECKING:
    from gmailapi.gmail import Gmail
    from gmailapi.message import Message
    from gmailapi.query import Query


class BaseLabel:
    def __init__(self, label_id: str, *, gmail: Gmail) -> None:
        self.id, self.gmail = label_id, gmail
        self.refresh()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={repr(self.name)}, messages_total={repr(self.messages_total)}, messages_unread={repr(self.messages_unread)})"

    def __str__(self) -> str:
        return self.name

    def __call__(self) -> BaseLabel:
        return self.refresh()

    def __hash__(self) -> int:
        return hash(self.id)

    def __getitem__(self, name: str) -> BaseLabel:
        return self.gmail.labels._registry.get_by_id(self.id).children[name].entity

    @property
    def messages(self) -> Query:
        return self.gmail.messages.labels(self)

    def refresh(self) -> BaseLabel:
        self.resource = Dict(self.gmail.service.users().labels().get(userId="me", id=self.id).execute())

        self.id, self.name, self.type = self.resource.id, self.resource.name, self.resource.get("type", "user")
        self.messages_total, self.messages_unread = self.resource.messagesTotal, self.resource.messagesUnread
        self.threads_total, self.threads_unread = self.resource.threadsTotal, self.resource.threadsUnread
        self.message_list_visibility, self.label_list_visibility = self.resource.get("messageListVisibility"), self.resource.get("labelListVisibility")
        return self


class Category(BaseLabel):
    def __contains__(self, other: Message) -> bool:
        if isinstance(other, self.gmail.Constructors.Message):
            return self == other.category
        else:
            raise TypeError(f"Cannot test '{type(other).__name__}' object for membership in a '{type(self).__name__}' object. Must be type '{Message.__name__}'.")

    def refresh(self) -> None:
        from .accessor import SystemCategories

        super().refresh()
        self.name = SystemCategories._id_name_mappings[self.id]


class Label(BaseLabel):
    def __contains__(self, other: Union[BaseLabel, Message]) -> bool:
        if isinstance(other, BaseLabel):
            return other.name in self.name
        elif isinstance(other, self.gmail.Constructors.Message):
            return self in other.labels
        else:
            raise TypeError(f"Cannot test '{type(other).__name__}' object for membership in a '{type(self).__name__}' object. Must be type '{BaseLabel.__name__}' or '{Message.__name__}'.")


class UserLabel(Label):
    @property
    def parent(self) -> BaseLabel:
        return self.gmail.labels._registry.get_by_id(self.id).parent.entity

    @property
    def children(self) -> list[BaseLabel]:
        return [node.entity for node in self.gmail.labels._registry.get_by_id(self.id).children.values()]

    def create_child(self, name: str, label_list_visibility: str = "labelShow", message_list_visibility: set = "show",
                     text_color: str = None, background_color: str = None) -> BaseLabel:
        return self.gmail.create_label(name=f"{self.name}/{name}", label_list_visibility=label_list_visibility, message_list_visibility=message_list_visibility,
                                       text_color=text_color, background_color=background_color)

    def update(self, name: str = None, label_list_visibility: str = None, message_list_visibility: set = None,
               text_color: str = None, background_color: str = None) -> BaseLabel:
        color = {
            name: val for name, val in {"textColor": text_color, "backgroundColor": background_color}.items() if val is not None
        } if text_color or background_color else None
        body = {
            name: val for name, val in {
                "name": name, "labelListVisibility": label_list_visibility, "messageListVisibility": message_list_visibility, "color": color
            }.items() if val is not None
        }

        if not body:
            raise RuntimeError(f"Cannot call {type(self).__name__}.{self.update.__name__} without arguments.")
        else:
            body["id"] = self.id
            self.gmail.service.users().labels().update(userId="me", id=self.id, body=body).execute()
            self.refresh()
            self.gmail._refresh_labels()

        return self

    def delete(self, recursive: bool = False) -> None:
        self.gmail.service.users().labels().delete(userId="me", id=self.id).execute()

        if recursive:
            for label in Dict(self.gmail.service.users().labels().list(userId="me").execute()).labels:
                if label.name.startswith(f"{self.name}/") and label.type == "user":
                    self.gmail.service.users().labels().delete(userId="me", id=label.id).execute()

        self.gmail._refresh_labels()

    @classmethod
    def create(cls, name: str, label_list_visibility: str = "labelShow", message_list_visibility: set = "show", text_color: str = None, background_color: str = None, *, gmail: Gmail) -> UserLabel:
        label = {"name": name, "labelListVisibility": label_list_visibility, "messageListVisibility": message_list_visibility}

        if text_color or background_color:
            color = {name: val for name, val in {"textColor": text_color, "backgroundColor": background_color}.items() if val is not None}
            if color:
                label["color"] = color

        label = cls(label_id=gmail.service.users().labels().create(userId="me", body=label).execute()["id"], gmail=gmail)
        gmail._refresh_labels()
        return label


class SystemLabel(Label):
    def refresh(self) -> None:
        from .accessor import SystemLabels

        super().refresh()
        self.name = SystemLabels._id_name_mappings[self.id]
