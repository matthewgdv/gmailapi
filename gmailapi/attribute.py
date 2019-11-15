from __future__ import annotations

from typing import Any, Union

from subtypes import Enum, Str


class Operator(Enum):
    EQUAL, NOT_EQUAL, GREATER, LESS, CONTAINS = "__eq__", "__ne__", "__gt__", "__lt__", "__contains__"


class ChainOperator(Enum):
    AND, OR = "__and__", "__or__"


class ComparableName:
    def __init__(self, name: str, less: str, greater: str) -> None:
        self.name, self.less, self.greater = name, less, greater

    def __str__(self) -> str:
        return self.name


class BaseAttributeMeta(type):
    """The metaclass shared by all attributes, implementing operator functionality."""

    name: str

    def __hash__(cls) -> int:
        return id(cls)

    def __and__(cls, other: Any) -> Expression:
        return cls._resolve() & other._resolve()

    def __or__(cls, other: Any) -> Expression:
        return cls._resolve() | other._resolve()

    def _resolve(cls) -> Any:
        raise ValueError(f"Cannot resolve an object of type '{cls.__name__}' without using it as part of a boolean expression.")


class BooleanAttributeMeta(BaseAttributeMeta):
    """A metaclass for boolean attributes which allows them to be automatically resolved to a True boolean expression, or inverted ('~' operator) for a False one."""

    def __invert__(cls) -> BooleanAttribute:
        return cls(Operator.NOT_EQUAL, True)


class EnumerativeAttributeMeta(BaseAttributeMeta):
    """A metaclass for enumerative attributes which dynamically creates methods that resolve them to a boolean expression based on an enumeration."""

    def __new__(mcs, name: str, bases: tuple, attributes: dict) -> Any:
        for val in attributes.values():
            if isinstance(val, BooleanAttributeMeta):
                val.owner = attributes["name"]

        return type.__new__(mcs, name, bases, attributes)


class EquatableAttributeMeta(BaseAttributeMeta):
    def __hash__(cls) -> int:
        return id(cls)

    def __eq__(cls, other: Any) -> EquatableAttribute:
        return cls(Operator.EQUAL, other)

    def __ne__(cls, other: Any) -> EquatableAttribute:
        return cls(Operator.NOT_EQUAL, other)

    def contains(cls, item: str) -> EquatableAttribute:
        """Return a boolean expression indicating whether this attribute contains the given value."""
        return cls(Operator.CONTAINS, item)


class ComparableAttributeMeta(BaseAttributeMeta):
    def __gt__(cls, other: Any) -> ComparableAttribute:
        return cls(Operator.GREATER, other)

    def __lt__(cls, other: Any) -> ComparableAttribute:
        return cls(Operator.LESS, other)


class BaseAttribute:
    """An abstract base class for all attributes to inherit from, providing basic functionality."""
    name: str

    def __init__(self, operator: Operator, value: Any) -> None:
        self.operator, self.value, self.negated = operator, value, False

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"""{self.prefix()}{self.left()}:{self.right()}"""

    def __and__(self, other: Union[BaseAttribute, Expression]) -> Expression:
        return Expression(left=self, operator=ChainOperator.AND, right=other._resolve())

    def __or__(self, other: Union[BaseAttribute, Expression]) -> Expression:
        return Expression(left=self, operator=ChainOperator.OR, right=other._resolve())

    def prefix(self) -> str:
        negated = not self.negated if self.operator == Operator.NOT_EQUAL else self.negated
        return "-" if negated else ""

    def left(self) -> str:
        return self.name

    def right(self) -> str:
        return str(self.value)

    def _resolve(self) -> BaseAttribute:
        return self


class BooleanAttribute(BaseAttribute, metaclass=BooleanAttributeMeta):
    """A class for boolean attributes to inherit from."""
    owner: str

    def prefix(self) -> str:
        if self.operator == Operator.EQUAL:
            truth = True
        elif self.operator == Operator.NOT_EQUAL:
            truth = False
        else:
            raise ValueError(f"Invalid operator: '{self.operator}' for attribute of type '{type(self).__name__}'.")

        return '' if (not truth if self.negated else truth) else '-'

    def left(self) -> str:
        return self.owner

    def right(self) -> str:
        return self.name

    @classmethod
    def _resolve(cls) -> BooleanAttribute:
        return cls(Operator.EQUAL, True)


class EnumerativeAttribute(BaseAttribute, metaclass=EnumerativeAttributeMeta):
    """A class for attributes to inherit from which always compare their value against a finite set of strings."""

    def __str__(self) -> str:
        raise TypeError(f"Cannot compile attribute of type {type(self).__name__}.")


class EquatableAttribute(BaseAttribute, metaclass=EquatableAttributeMeta):
    def __str__(self) -> str:
        return f"{'-' if self.negated else ''}{self.name}:{self.value}"

    def right(self) -> str:
        value = Str(self.value).re.split(r"\s")[0]
        if self.operator == Operator.CONTAINS:
            return value
        elif self.operator in (Operator.EQUAL, Operator.NOT_EQUAL):
            return f'"{value}"'
        else:
            raise ValueError(f"Invalid operator: '{self.operator}' for attribute of type '{type(self).__name__}'.")


class ComparableAttribute(BaseAttribute, metaclass=ComparableAttributeMeta):
    def left(self) -> str:
        if self.operator == Operator.GREATER:
            return self.name.greater
        elif self.operator == Operator.LESS:
            return self.name.less
        else:
            raise ValueError(f"Invalid operator: '{self.operator}' for attribute of type '{type(self).__name__}'.")

    def right(self) -> str:
        return Str(self.value).re.split(r"\s")[0]


class Expression:
    """A class representing a binary clause of where each side contains either an instanciated attribute or another expression."""

    negated: bool
    parentheses = {
        ChainOperator.AND: ("(", ")"),
        ChainOperator.OR: ("{", "}")
    }

    def __init__(self, left: Union[BaseAttribute, Expression], operator: ChainOperator, right: Union[BaseAttribute, Expression]) -> None:
        self.left, self.operator, self.right = left, operator, right

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        start, stop = self.parentheses[self.operator]
        return f"""{start}{self.left} {self.right}{stop}"""

    def __and__(self, other: Union[BaseAttribute, Expression]) -> Expression:
        return Expression(left=self, operator=ChainOperator.AND, right=other)

    def __or__(self, other: Union[BaseAttribute, Expression]) -> Expression:
        return Expression(left=self, operator=ChainOperator.OR, right=other)

    def __invert__(self) -> Expression:
        return self._negate()

    def _negate(self) -> Expression:
        """Negate this boolean expression by either using the logically oposite operator, or, if none exists, using the 'not' logical operator."""
        self.negated = not self.negated
        return self

    def _resolve(self) -> Expression:
        return self


class Attributes:
    class From(EquatableAttribute):
        name = "from"

    class To(EquatableAttribute):
        name = "to"

    class Cc(EquatableAttribute):
        name = "cc"

    class Bcc(EquatableAttribute):
        name = "bcc"

    class Subject(EquatableAttribute):
        name = "subject"

    class FileName(EquatableAttribute):
        name = "filename"

    class Date(ComparableAttribute):
        name = ComparableName("date", greater="after", less="before")

    class Size(ComparableAttribute):
        name = ComparableName("size", greater="larger", less="smaller")

    class Has(EnumerativeAttribute):
        name = "has"

        class Attachment(BooleanAttribute):
            name = "attachment"

        class YoutubeVideo(BooleanAttribute):
            name = "youtube"

        class GoogleDrive(BooleanAttribute):
            name = "drive"

        class GoogleDocs(BooleanAttribute):
            name = "document"

        class GoogleSheets(BooleanAttribute):
            name = "spreadsheet"

        class GoogleSlides(BooleanAttribute):
            name = "presentation"

        class UserLabel(BooleanAttribute):
            name = "userlabels"
