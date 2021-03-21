from __future__ import annotations

from typing import TYPE_CHECKING

from subtypes import NameSpace

from .registry import Registry
from .mapper import LabelMapper, CategoryMapper
from .hierarchy import Root

if TYPE_CHECKING:
    from gmailapi.gmail import Gmail


class SystemLabels:
    _id_name_mappings = {
        "INBOX": "Inbox",
        "SENT": "Sent",
        "UNREAD": "Unread",
        "IMPORTANT": "Important",
        "STARRED": "Starred",
        "DRAFT": "Draft",
        "CHAT": "Chat",
        "TRASH": "Trash",
        "SPAM": "Spam"
    }

    def __init__(self, gmail: Gmail) -> None:
        self._gmail = gmail
        self.inbox = LabelMapper(id_="INBOX", name=self._id_name_mappings["INBOX"], gmail=self._gmail).proxy
        self.sent = LabelMapper(id_="SENT", name=self._id_name_mappings["SENT"], gmail=self._gmail).proxy
        self.unread = LabelMapper(id_="UNREAD", name=self._id_name_mappings["UNREAD"], gmail=self._gmail).proxy
        self.important = LabelMapper(id_="IMPORTANT", name=self._id_name_mappings["IMPORTANT"], gmail=self._gmail).proxy
        self.starred = LabelMapper(id_="STARRED", name=self._id_name_mappings["STARRED"], gmail=self._gmail).proxy
        self.draft = LabelMapper(id_="DRAFT", name=self._id_name_mappings["DRAFT"], gmail=self._gmail).proxy
        self.chat = LabelMapper(id_="CHAT", name=self._id_name_mappings["CHAT"], gmail=self._gmail).proxy
        self.trash = LabelMapper(id_="TRASH", name=self._id_name_mappings["TRASH"], gmail=self._gmail).proxy
        self.spam = LabelMapper(id_="SPAM", name=self._id_name_mappings["SPAM"], gmail=self._gmail).proxy


class SystemCategories:
    _id_name_mappings = {
        "CATEGORY_PERSONAL": "Primary",
        "CATEGORY_SOCIAL": "Social",
        "CATEGORY_PROMOTIONS": "Promotions",
        "CATEGORY_UPDATES": "Updates",
        "CATEGORY_FORUMS": "Forums"
    }

    def __init__(self, gmail: Gmail) -> None:
        self._gmail = gmail
        self.primary = CategoryMapper(id_="CATEGORY_PERSONAL", name=self._id_name_mappings["CATEGORY_PERSONAL"], gmail=self._gmail).proxy
        self.social = CategoryMapper(id_="CATEGORY_SOCIAL", name=self._id_name_mappings["CATEGORY_SOCIAL"], gmail=self._gmail).proxy
        self.promotions = CategoryMapper(id_="CATEGORY_PROMOTIONS", name=self._id_name_mappings["CATEGORY_PROMOTIONS"], gmail=self._gmail).proxy
        self.updates = CategoryMapper(id_="CATEGORY_UPDATES", name=self._id_name_mappings["CATEGORY_UPDATES"], gmail=self._gmail).proxy
        self.forums = CategoryMapper(id_="CATEGORY_FORUMS", name=self._id_name_mappings["CATEGORY_FORUMS"], gmail=self._gmail).proxy


class LabelAccessor:
    _system_ids = set(SystemLabels._id_name_mappings) | set(SystemCategories._id_name_mappings)

    def __init__(self, gmail: Gmail) -> None:
        self._gmail = gmail

        self.categories = SystemCategories(gmail=self._gmail)
        self.system = SystemLabels(gmail=self._gmail)
        self.user = NameSpace()

        self._registry = None

        self._refresh()

    def _refresh(self) -> None:
        new_registry = self._prepare_new_registry()
        old_registry = self._registry if self._registry is not None else Registry()
        Root(self._gmail).refresh(old_registry=old_registry, new_registry=new_registry, root_namespace=self.user)
        self._registry = new_registry

    def _prepare_new_registry(self) -> Registry:
        registry = Registry()

        for proxy in [
            self.categories.primary, self.categories.social, self.categories.promotions, self.categories.updates, self.categories.forums,
            self.system.inbox, self.system.sent, self.system.unread, self.system.important,
            self.system.starred, self.system.draft, self.system.chat, self.system.trash, self.system.spam
        ]:
            registry.set(proxy._mapper_)

        return registry
