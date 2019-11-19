from __future__ import annotations

import time
from typing import Any, List, Callable, Collection, Union, TYPE_CHECKING

from googleapiclient.discovery import BatchHttpRequest

from subtypes import Dict_
from miscutils import OneOrMany, Timer

from .attribute import BaseAttributeMeta, BaseAttribute, Expression, OrderableAttributeMixin, Direction
from .message import Message
from .label import BaseLabel, Label, Category

if TYPE_CHECKING:
    from .gmail import Gmail


class Query:
    """A class for querying the api elements within a given collection."""

    def __init__(self, gmail: Gmail) -> None:
        self._gmail = gmail
        self._select: str = None
        self._where: str = None
        self._labels: List[BaseLabel] = None
        self._limit: int = self._gmail.BATCH_SIZE or 25
        self._trash = False
        self._order: List[OrderableAttributeMixin] = None

    def __repr__(self) -> str:
        labels = None if self._labels is None else [label.name for label in self._labels]
        order_by = None if self._order is None else [f"{order.attr} {order.direction}" for order in self._order]
        return f"{type(self).__name__}(select={repr(self._select)}, where={repr(self._where)}, labels={repr(labels)}, limit={self._limit}, include_trash={self._trash}, order_by={repr(order_by)})"

    def __call__(self) -> Any:
        return self.execute()

    @property
    def bulk(self) -> BulkAction:
        """Perform a bulk action on the resultset of this query."""
        return BulkAction(self)

    def select(self, detail_level: Message.Format) -> Query:
        """Set the attributes that will be queried. If this method is not called, all message attributes will be returned."""
        Message.Format.raise_if_not_a_member(detail_level)
        self._select = detail_level.value
        return self

    def where(self, expression: Union[BaseAttributeMeta, BaseAttribute, Expression]) -> Query:
        """Set the filter clause on this query. Accepts a single boolean attribute, boolean expression or boolean expression clause."""
        self._where = str(expression._resolve() if isinstance(expression, BaseAttributeMeta) else expression)
        return self

    def labels(self, labels: Union[BaseLabel, Collection[BaseLabel]]) -> Query:
        self._labels = OneOrMany(of_type=BaseLabel).to_list(labels)
        return self

    def order_by(self, order_clause: Union[OrderableAttributeMixin, Collection[OrderableAttributeMixin]]) -> Query:
        """Set the filter clause on this query. Accepts a single boolean attribute, boolean expression or boolean expression clause."""
        self._order = OneOrMany(of_type=OrderableAttributeMixin).to_list(order_clause)
        return self

    def limit(self, limit: int = 25) -> Query:
        """Set the limit on the number of objects that may be returned."""
        self._limit = limit
        return self

    def include_trash(self, include_trash: bool = True) -> Query:
        self._trash = include_trash
        return self

    def execute(self) -> Any:
        """Execute this query and return the results."""
        message_ids = self._fetch_message_ids()
        if self._gmail.BATCH_SIZE is None:
            messages = [self._gmail.Constructors.Message.from_id(message_id=message_id, gmail=self._gmail) for message_id in message_ids]
        else:
            messages = sum([self._fetch_messages_in_batch(message_ids[index:index + self._gmail.BATCH_SIZE]) for index in range(0, len(message_ids), self._gmail.BATCH_SIZE)], [])

        return messages if self._order is None else self._apply_ordering_to_messages(messages)

    def _fetch_message_ids(self) -> List[int]:
        kwargs = {
            key: val for key, val in
            {"q": self._where,
             "labelIds": None if self._labels is None else [label.id for label in self._labels],
             "maxResults": self._limit,
             "includeSpamTrash": self._trash}.items()
            if val
        }

        response = Dict_(self._gmail.service.users().messages().list(userId="me", **kwargs).execute())
        resources = response.get("messages", [])

        kwargs["maxResults"] = 500 if self._limit is None else self._limit - len(resources)
        while kwargs["maxResults"] > 0 and "nextPageToken" in response:
            response = Dict_(self._gmail.service.users().messages().list(userId="me", pageToken=response.nextPageToken, **kwargs).execute())
            resources += response.messages

            kwargs["maxResults"] = 500 if self._limit is None else self._limit - len(resources)

        return [resouce.id for resouce in resources]

    def _fetch_messages_in_batch(self, message_ids: List[str], batch_delay: int = 1) -> List[Message]:
        def append_to_list(response_id: str, response: dict, exception: Exception) -> None:
            if exception is not None:
                raise exception

            resources.append(Dict_(response))

        timer, resources, batch = Timer(), [], BatchHttpRequest(callback=append_to_list)
        for message_id in message_ids:
            batch.add(self._gmail.service.users().messages().get(userId="me", id=message_id))

        batch.execute()
        messages = [self._gmail.Constructors.Message(resource=resource, gmail=self._gmail) for resource in resources]

        while timer < self._gmail.BATCH_DELAY_SECONDS:
            time.sleep(0.05)

        return messages

    def _apply_ordering_to_messages(self, messages: List[Message]) -> List[Message]:
        for attribute in reversed(self._order):
            messages = sorted(messages, key=lambda msg: getattr(msg, attribute.attr), reverse=True if attribute.direction == Direction.DESCENDING else False)

        return messages


class BulkActionContext:
    """A class representing the context within which a bulk action is performed. It can be used as a context manager and will automatically perform the action upon dropping out of scope if the action was committed."""

    def __init__(self, action: Callable) -> None:
        self._action, self._committed = action, False
        self.result_set: List[str] = None

    def __len__(self) -> int:
        return len(self.result_set)

    def __bool__(self) -> bool:
        return len(self) > 0

    def __enter__(self) -> BulkActionContext:
        self.result_set = self._query._fetch_message_ids()
        return self

    def __exit__(self, ex_type: Any, ex_value: Any, ex_traceback: Any) -> None:
        if self._committed:
            self._action.execute()

    def commit(self) -> None:
        """Commit the action corresponding to this context. It will be performed when this object drops out of context."""
        self._committed = True

    def execute(self) -> int:
        """Perform the bulk action corresponding to this context."""
        self.result_set = self._query._fetch_message_ids()
        self._action.execute()
        return len(self)


class BulkAction:
    """A class representing a bulk action performed on the resultset of a query."""

    def __init__(self, gmail: Gmail) -> None:
        self._gmail = gmail

    def delete(self) -> BulkActionContext:
        return BulkActionContext(action=lambda results: self._gmail.service.users().messages().batchDelete(userId="me", body={"ids": results}))

    def change_category_to(self, category: Category) -> BulkActionContext:
        if isinstance(category, self.gmail.Constructors.Category):
            return BulkActionContext(action=lambda results: self._gmail.service.users().messages().batchModify(userId="me", body={"ids": results, "addLabelIds": [category.id]}))
        else:
            raise TypeError(f"Argument to '{self.change_category_to.__name__}' must be of type '{self.gmail.Constructors.Category.__name__}', not '{type(category).__name__}'.")

    def add_labels(self, labels: Union[Label, Collection[Label]]) -> BulkActionContext:
        label_ids = OneOrMany(of_type=self.gmail.Constructors.Label).to_list(labels)
        return BulkActionContext(action=lambda results: self._gmail.service.users().messages().batchModify(userId="me", body={"ids": results, "addLabelIds": label_ids}))

    def remove_labels(self, labels: Union[Label, Collection[Label]]) -> BulkActionContext:
        label_ids = OneOrMany(of_type=self.gmail.Constructors.Label).to_list(labels)
        return BulkActionContext(action=lambda results: self._gmail.service.users().messages().batchModify(userId="me", body={"ids": results, "removeLabelIds": label_ids}))

    def mark_is_read(self, is_read: bool = True) -> BulkActionContext:
        return self.remove_labels(self._gmail.labels.UNREAD()) if is_read else self.add_labels(self.gmail.labels.UNREAD())

    def mark_is_important(self, is_important: bool = True) -> BulkActionContext:
        return self.add_labels(self._gmail.labels.IMPORTANT()) if is_important else self.remove_labels(self.gmail.labels.IMPORTANT())

    def mark_is_starred(self, is_starred: bool = True) -> BulkActionContext:
        return self.add_labels(self._gmail.labels.STARRED()) if is_starred else self.remove_labels(self.gmail.labels.STARRED())

    def archive(self) -> BulkActionContext:
        return self.remove_labels(self._gmail.labels.INBOX())
