from __future__ import annotations

from typing import Any, TYPE_CHECKING, Optional

from subtypes import NameSpace

if TYPE_CHECKING:
    from .label import Category, Label
    from .mapper import BaseMapper


class BaseProxy(NameSpace):
    def __init__(self, mapper: BaseMapper) -> None:
        self._mapper_ = mapper

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join([f'{repr(self._mapper_.name)}', *[f'{attr}={repr(val)}' for attr, val in self]])})"


class LabelProxy(BaseProxy):
    def __call__(self, mapping: dict = None, /, **kwargs: Any) -> Optional[Label]:
        if mapping is None and not kwargs:
            return self._mapper_.entity
        else:
            super().__call__(mapping, **kwargs)


class CategoryProxy(BaseProxy):
    def __call__(self, mapping: dict = None, /, **kwargs: Any) -> Optional[Category]:
        if mapping is None and not kwargs:
            return self._mapper_.entity
        else:
            super().__call__(mapping, **kwargs)
