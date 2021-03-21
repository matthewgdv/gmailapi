from __future__ import annotations

from typing import Any, TYPE_CHECKING, Optional, Type

from miscutils import ReprMixin

from .proxy import BaseProxy, LabelProxy, CategoryProxy
from .label import BaseLabel, Label, Category

if TYPE_CHECKING:
    from gmailapi.gmail import Gmail


class BaseMapper(ReprMixin):
    def __init__(self, gmail: Gmail, id_: str, name: str) -> None:
        self.gmail, self.id, self.name = gmail, id_, name

        self.proxy: Optional[BaseProxy] = self.proxy_constructor(mapper=self)
        self._entity: Optional[BaseLabel] = None

    @property
    def proxy_constructor(self) -> Type[BaseProxy]:
        raise NotImplementedError

    @property
    def entity_constructor(self):
        raise NotImplementedError

    @property
    def entity(self) -> Any:
        if self._entity is None:
            self._entity = self.entity_constructor(label_id=self.id, gmail=self.gmail)

        return self._entity


class LabelMapper(BaseMapper):
    def __init__(self, gmail: Gmail, id_: str, name: str) -> None:
        super().__init__(gmail=gmail, id_=id_, name=name)

    @property
    def proxy_constructor(self) -> Type[LabelProxy]:
        return LabelProxy

    @property
    def entity_constructor(self) -> Type[Label]:
        from .accessor import SystemLabels
        return self.gmail.Constructors.SystemLabel if self.id in SystemLabels._id_name_mappings else self.gmail.Constructors.UserLabel

    @property
    def entity(self) -> Label:
        return super().entity


class CategoryMapper(BaseMapper):
    @property
    def proxy_constructor(self):
        return CategoryProxy

    @property
    def entity_constructor(self):
        return self.gmail.Constructors.Category

    @property
    def entity(self) -> Category:
        return super().entity
