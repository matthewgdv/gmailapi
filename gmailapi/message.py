from __future__ import annotations

from typing import Any, List, Tuple, Union, Collection, Optional, TYPE_CHECKING
from html import unescape

import mailparser

from pathmagic import File, Dir, PathLike
from subtypes import Dict_, BaseList, DateTime, Markup
from miscutils import OneOrMany, Base64
from iotools import HtmlGui

from .draft import MessageDraft
from .attribute import EquatableAttribute, ComparableAttribute, BooleanAttribute, EnumerableAttribute, OrderableAttributeMixin, ComparableName

if TYPE_CHECKING:
    from .gmail import Gmail
    from .label import BaseLabel, Label, Category


class Message:
    def __init__(self, resource: Dict_, gmail: Gmail) -> None:
        self.resource, self.gmail = resource, gmail
        self._set_attributes_from_resource()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(subject={repr(self.subject)}, from={repr(str(self.from_))}, to={repr([str(contact) for contact in self.to])}, date='{self.date}')"

    def __str__(self) -> str:
        return self.body.text

    def __call__(self) -> Message:
        return self.refresh()

    def __hash__(self) -> int:
        return hash(self.id)

    def __contains__(self, other: BaseLabel) -> bool:
        from .label import BaseLabel

        if isinstance(other, BaseLabel):
            return other in self.labels or other == self.category
        else:
            raise TypeError(f"Cannot test '{type(other).__name__}' object for membership in a '{type(self).__name__}' object. Must be type '{BaseLabel.__name__}'.")

    @property
    def markup(self) -> Markup:
        """A property controlling access to the subtypes.Markup object corresponding to this message's html body."""
        return Markup(self.body.html)

    def render(self) -> None:
        """Render the message body html in a separate window. Will block until the window has been closed by a user."""
        HtmlGui(name=self.subject, text=self.body.html).start()

    def change_category_to(self, category: Category) -> Message:
        if isinstance(category, self.gmail.constructors.Category):
            self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"removeLabelIds": self.category.id, "addLabelIds": category.id}).execute()
            self.refresh()
        else:
            raise TypeError(f"Argument to '{self.change_category_to.__name__}' must be of type '{self.gmail.constructors.Category.__name__}', not '{type(category).__name__}'.")

        return self

    def add_labels(self, labels: Union[Label, Collection[Label]]) -> Message:
        self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"addLabelIds": OneOrMany(of_type=self.gmail.constructors.Label).to_list(labels)}).execute()
        self.refresh()
        return self

    def remove_labels(self, labels: Union[Label, Collection[Label]]) -> Message:
        self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"removeLabelIds": OneOrMany(of_type=self.gmail.constructors.Label).to_list(labels)}).execute()
        self.refresh()
        return self

    def mark_is_read(self, is_read: bool = True) -> Message:
        self.remove_labels(self.gmail.labels.UNREAD()) if is_read else self.add_labels(self.gmail.labels.UNREAD())
        return self

    def mark_is_important(self, is_important: bool = True) -> Message:
        self.add_labels(self.gmail.labels.IMPORTANT()) if is_important else self.remove_labels(self.gmail.labels.IMPORTANT())
        return self

    def mark_is_starred(self, is_starred: bool = True) -> Message:
        self.add_labels(self.gmail.labels.STARRED()) if is_starred else self.remove_labels(self.gmail.labels.STARRED())
        return self

    def archive(self) -> Message:
        self.remove_labels(self.gmail.labels.INBOX())
        return self

    def trash(self) -> Message:
        self.gmail.service.users().messages().trash(userId="me", id=self.id).execute()
        self.refresh()
        return self

    def untrash(self) -> Message:
        self.gmail.service.users().messages().untrash(userId="me", id=self.id).execute()
        self.refresh()
        return self

    def delete(self) -> Message:
        self.gmail.service.users().messages().delete(userId="me", id=self.id).execute()
        return self

    def reply(self) -> MessageDraft:
        return MessageDraft(gmail=self.gmail, parent=self).to(self.from_).subject(f"RE: {self.subject}")

    def forward(self) -> MessageDraft:
        return MessageDraft(gmail=self.gmail, parent=self).subject(f"FWD: {self.subject}")

    def refresh(self) -> Message:
        self.resource = Dict_(self.gmail.service.users().messages().get(userId="me", id=self.id, format="raw").execute())
        self._set_attributes_from_resource()
        return self

    def _set_attributes_from_resource(self) -> None:
        self.id, self.thread_id, self.size = self.resource.id, self.resource.threadId, self.resource.sizeEstimate
        self.date = DateTime.fromtimestamp(int(self.resource.internalDate)/1000)

        self.parsed = mailparser.parse_from_bytes(Base64.from_b64(self.resource.raw).bytes)

        self.subject = self.parsed.subject
        self.from_ = self.gmail.constructors.Contact.or_none(self.parsed.from_)
        self.to = self.gmail.constructors.Contact.many_or_none(self.parsed.to)
        self.cc = self.gmail.constructors.Contact.many_or_none(self.parsed.cc)
        self.bcc = self.gmail.constructors.Contact.many_or_none(self.parsed.bcc)

        self.body = Body(text="\n\n".join(self.parsed.text_plain), html="\n\n".join(self.parsed.text_html))
        self.attachments = Attachments([Attachment(name=attachment["filename"], payload=attachment["payload"]) for attachment in self.parsed.attachments])

        all_labels = [self.gmail.labels._id_mappings_[label_id]() for label_id in self.resource.get("labelIds", [])]
        self.labels = {label for label in all_labels if isinstance(label, self.gmail.constructors.Label)}
        self.category = OneOrMany(of_type=self.gmail.constructors.Category).to_one_or_none([label for label in all_labels if isinstance(label, self.gmail.constructors.Category)])

    @classmethod
    def from_id(cls, message_id: str, gmail: Gmail) -> Message:
        return cls(resource=Dict_(gmail.service.users().messages().get(userId="me", id=message_id, format="raw").execute()), gmail=gmail)

    class Attribute:
        class From(EquatableAttribute, OrderableAttributeMixin):
            name, attr = "from", "from_"

        class To(EquatableAttribute, OrderableAttributeMixin):
            name = attr = "to"

        class Cc(EquatableAttribute, OrderableAttributeMixin):
            name = attr = "cc"

        class Bcc(EquatableAttribute, OrderableAttributeMixin):
            name = attr = "bcc"

        class Subject(EquatableAttribute, OrderableAttributeMixin):
            name = attr = "subject"

        class FileName(EquatableAttribute):
            name = "filename"

        class Date(ComparableAttribute, OrderableAttributeMixin):
            name, attr = ComparableName("date", greater="after", less="before"), "date"

            def coerce(self, val: Any) -> str:
                return DateTime.from_datelike(val).to_isoformat(time=False)

        class Size(ComparableAttribute, OrderableAttributeMixin):
            name, attr = ComparableName("size", greater="larger", less="smaller"), "size"

        class Has(EnumerableAttribute):
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


class Contact:
    def __init__(self, name: str, address: str) -> None:
        self.name, self.address = name or None, address

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join([f'{attr}={repr(val)}' for attr, val in self.__dict__.items() if not attr.startswith('_')])})"

    def __str__(self) -> str:
        return self.address

    def __eq__(self, other: Any) -> bool:
        return str(self) == str(other)

    @classmethod
    def or_none(cls, contact_or_none: List[Tuple[str, str]]) -> Optional[Contact]:
        if contact_or_none:
            from_, = contact_or_none
            name, address = from_
            return cls(name=name, address=address)
        else:
            return None

    @classmethod
    def many_or_none(cls, contacts_or_none: str = None) -> Optional[List[Contact]]:
        return [cls(name=name, address=address) for name, address in contacts_or_none] if contacts_or_none else None


class Body:
    def __init__(self, text: str = None, html: str = None) -> None:
        self.text, self.html, self.raw = text, unescape(html), html

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join([f'{attr}={repr(val)}' for attr, val in self.__dict__.items() if not attr.startswith('_')])})"

    def __str__(self) -> str:
        return self.text

    def _repr_html_(self) -> str:
        return self.raw


class Attachments(BaseList):
    def save_to(self, folder: PathLike) -> List[File]:
        return [attachment.save_to(folder) for attachment in self]


class Attachment:
    def __init__(self, name: str, payload: str) -> None:
        self.name, self.payload = name, payload

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={repr(self.name)})"

    def save_to(self, folder: PathLike) -> File:
        return self._save(Dir.from_pathlike(folder).new_file(self.name))

    def save_as(self, file: PathLike) -> File:
        return self._save(File.from_pathlike(file))

    def _save(self, file: PathLike) -> File:
        (file := File.from_pathlike(file)).path.write_bytes(Base64.from_b64(self.payload).bytes)
        return file
