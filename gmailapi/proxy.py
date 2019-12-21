from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from subtypes import Dict_, NameSpace

if TYPE_CHECKING:
    from .gmail import Gmail
    from .label import Category, Label, BaseLabel


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

    @property
    def inbox(self) -> LabelProxy:
        return self._gmail.labels.Inbox

    @property
    def sent(self) -> LabelProxy:
        return self._gmail.labels.Sent

    @property
    def unread(self) -> LabelProxy:
        return self._gmail.labels.Unread

    @property
    def important(self) -> LabelProxy:
        return self._gmail.labels.Important

    @property
    def starred(self) -> LabelProxy:
        return self._gmail.labels.Starred

    @property
    def draft(self) -> LabelProxy:
        return self._gmail.labels.Draft

    @property
    def chat(self) -> LabelProxy:
        return self._gmail.labels.Chat

    @property
    def trash(self) -> LabelProxy:
        return self._gmail.labels.Trash

    @property
    def spam(self) -> LabelProxy:
        return self._gmail.labels.Spam


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
        self.primary = CategoryProxy(entity_id="CATEGORY_PERSONAL", entity_name=self._id_name_mappings["CATEGORY_PERSONAL"], gmail=self._gmail)
        self.social = CategoryProxy(entity_id="CATEGORY_SOCIAL", entity_name=self._id_name_mappings["CATEGORY_SOCIAL"], gmail=self._gmail)
        self.promotions = CategoryProxy(entity_id="CATEGORY_PROMOTIONS", entity_name=self._id_name_mappings["CATEGORY_PROMOTIONS"], gmail=self._gmail)
        self.updates = CategoryProxy(entity_id="CATEGORY_UPDATES", entity_name=self._id_name_mappings["CATEGORY_UPDATES"], gmail=self._gmail)
        self.forums = CategoryProxy(entity_id="CATEGORY_FORUMS", entity_name=self._id_name_mappings["CATEGORY_FORUMS"], gmail=self._gmail)


class SystemDefaults:
    _ids = set(SystemLabels._id_name_mappings) | set(SystemCategories._id_name_mappings)

    def __init__(self, gmail: Gmail) -> None:
        self._gmail = gmail
        self.labels = SystemLabels(gmail=self._gmail)
        self.categories = SystemCategories(gmail=self._gmail)


class LabelAccessor(NameSpace):
    def __init__(self, gmail: Gmail) -> None:
        self._gmail_, self._id_mappings_, self._name_mappings_ = gmail, {}, {}

    def _regenerate_label_tree(self) -> LabelAccessor:
        self._gmail_.expire(), self()

        labels = Dict_(self._gmail_.service.users().labels().list(userId="me").execute()).labels
        real_labels = [label for label in labels if label.id not in SystemCategories._id_name_mappings]

        existing_label_ids = {label.id for label in real_labels}
        old_label_ids = {label_id for label_id in self._id_mappings_ if label_id not in {*existing_label_ids, *SystemCategories._id_name_mappings}}
        for label_id in old_label_ids:
            self._name_mappings_.pop(self._id_mappings_.pop(label_id)._entity_name_)

        for label in real_labels:
            if label.id in SystemLabels._id_name_mappings:
                label.name = SystemLabels._id_name_mappings[label.id]

            node, iterable = self, [level for level in label.name.split('/') if level] or [label.name]
            for index, level in enumerate(iterable):
                if level in node:
                    node = node[level]
                else:
                    if label.id in self._id_mappings_:
                        proxy = self._id_mappings_[label.id]
                        proxy._entity_name_, proxy._parent_ = label.name, node if node is not self else None
                        proxy()
                    else:
                        proxy = LabelProxy(entity_id=label.id, entity_name=label.name, gmail=self._gmail_, parent=node if node is not self else None)

                    stem = level if index + 1 == len(iterable) else "/".join(iterable[index:])
                    node[stem] = proxy
                    break

        return self


class BaseProxy(NameSpace):
    def __init__(self, entity_id: str, entity_name: str, gmail: Gmail, parent: LabelProxy = None) -> None:
        self._entity_id_, self._entity_name_, self._gmail_, self._parent_ = entity_id, entity_name, gmail, parent
        self._entity_: Optional[BaseLabel] = None
        self._gmail_.labels._id_mappings_[entity_id] = self._gmail_.labels._name_mappings_[entity_name] = self

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join([f'{repr(self._entity_name_)}', *[f'{attr}={repr(val)}' for attr, val in self]])})"


class LabelProxy(BaseProxy):
    def __call__(self) -> Label:
        if self._entity_ is None:
            constructor = self._gmail_.constructors.SystemLabel if self._entity_id_ in SystemLabels._id_name_mappings else self._gmail_.constructors.UserLabel
            self._entity_ = constructor(label_id=self._entity_id_, gmail=self._gmail_)

        return self._entity_


class CategoryProxy(BaseProxy):
    def __call__(self) -> Category:
        if self._entity_ is None:
            self._entity_ = self._gmail_.constructors.Category(label_id=self._entity_id_, gmail=self._gmail_)

        return self._entity_
