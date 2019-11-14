from __future__ import annotations

import os
from typing import List, Union, Collection, TYPE_CHECKING
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from maybe import Maybe
from pathmagic import File, Dir, PathLike
from subtypes import Dict_, DateTime, Str, Markup
from miscutils import is_non_string_iterable, OneOrMany
from iotools import HtmlGui

if TYPE_CHECKING:
    from .gmail import Gmail
    from .label import BaseLabel, Label, Category


class Message:
    def __init__(self, resource: Dict_, gmail: Gmail) -> None:
        self.resource, self.gmail = resource, gmail
        self._set_attributes_from_resource()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(subject={repr(self.subject)}, from={repr(self.from_)}, to={repr(self.to)}, date='{self.date}')"

    def __str__(self) -> str:
        return self.text

    def __call__(self) -> BaseLabel:
        return self.refresh()

    def __hash__(self) -> int:
        return hash(self.id)

    def __contains__(self, other: BaseLabel) -> bool:
        from .label import BaseLabel

        if isinstance(other, BaseLabel):
            return other in self.labels or other == self.category
        else:
            raise TypeError(f"Cannot test '{type(other).__name__}' object for membership in a '{type(self).__name__}' object. Must be type '{BaseLabel.__name__}'.")

    def _repr_html_(self) -> str:
        return f"<strong><mark>{self.subject}</mark></strong><br><br>{self.body}"

    @property
    def markup(self) -> Markup:
        """A property controlling access to the subtypes.Markup object corresponding to this message's html body."""
        return Markup(self.body)

    def render(self) -> None:
        """Render the message body html in a separate window. Will block until the window has been closed by a user."""
        HtmlGui(name=self.subject, text=self.body).start()

    def save_attachments_to(self, directory: PathLike) -> List[File]:
        target_dir = Dir.from_pathlike(directory)
        files = []
        for part in (self.resource.payload.parts if "parts" in self.resource.payload else [self.resource.payload]):
            if part.filename:
                data = self.gmail.service.users().messages().attachments().get(userId="me", messageId=self.id, id=part.body.attachmentId).execute()["data"]

                file = target_dir.new_file(part.filename)
                file.path.write_bytes(base64.urlsafe_b64decode(data.encode("utf-8")))
                files.append(file)

        return files

    def change_category_to(self, category: Category) -> Message:
        if isinstance(category, self.gmail.Constructors.Category):
            self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"removeLabelIds": self.category.id, "addLabelIds": category.id}).execute()
            self.refresh()
        else:
            raise TypeError(f"Argument to '{self.change_category_to.__name__}' must be of type '{self.gmail.Constructors.Category.__name__}', not '{type(category).__name__}'.")

        return self

    def add_labels(self, labels: Union[Label, Collection[Label]]) -> Message:
        self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"addLabelIds": OneOrMany(of_type=self.gmail.Constructors.Label).to_list(labels)}).execute()
        self.refresh()
        return self

    def remove_labels(self, labels: Union[Label, Collection[Label]]) -> Message:
        self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"removeLabelIds": OneOrMany(of_type=self.gmail.Constructors.Label).to_list(labels)}).execute()
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

    def refresh(self) -> None:
        self.resource = Dict_(self.gmail.service.users().messages().get(userId="me", id=self.id, format="full").execute())
        self._set_attributes_from_resource()

    def _set_attributes_from_resource(self) -> None:
        self.id, self.thread_id = self.resource.id, self.resource.threadId
        self.date = DateTime.fromtimestamp(int(self.resource.internalDate)/1000)

        self.headers = Dict_({item.name.lower(): item for item in self.resource.payload.headers})
        self.subject = self._fetch_header_safely("subject")
        self.from_ = self._fetch_header_safely("from")
        self.to = self._fetch_header_safely("to")

        self.text = Str(self._recursively_extract_parts_by_mimetype("text/plain")).trim.whitespace_runs(newlines=2)
        self.body = self._recursively_extract_parts_by_mimetype("text/html")

        all_labels = [self.gmail.labels._id_mappings_[label_id]() for label_id in self.resource.get("labelIds", [])]
        self.labels = {label for label in all_labels if isinstance(label, self.gmail.Constructors.Label)}
        self.category = OneOrMany(of_type=self.gmail.Constructors.Category).to_one_or_none([label for label in all_labels if isinstance(label, self.gmail.Constructors.Category)])

    def _recursively_extract_parts_by_mimetype(self, mime_type: str) -> str:
        output = []

        def recurse(parts: list) -> None:
            for part in parts:
                if part.mimeType == mime_type:
                    if "data" in part.body:
                        output.append(self._decode_body(part.body.data))
                if "parts" in part:
                    recurse(parts=part.parts)

        recurse(parts=self.resource.payload.parts if "parts" in self.resource.payload else [self.resource.payload])
        return "".join(output)

    def _fetch_header_safely(self, header_name: str) -> str:
        return Maybe(self.headers)[header_name].value.else_(None)

    def _decode_body(self, body: str) -> str:
        return base64.urlsafe_b64decode(body).decode("utf-8")

    def _parse_datetime(self, datetime: str) -> DateTime:
        if datetime is None:
            return None
        else:
            Code = DateTime.FormatCode
            clean = " ".join(datetime.split(" ")[:5])
            return DateTime.strptime(clean, f"{Code.WEEKDAY.SHORT}, {Code.DAY.NUM} {Code.MONTH.SHORT} {Code.YEAR.WITH_CENTURY} {Code.HOUR.H24}:{Code.MINUTE.NUM}:{Code.SECOND.NUM}")

    @classmethod
    def from_id(cls, message_id: str, gmail: Gmail) -> Message:
        return cls(resource=Dict_(gmail.service.users().messages().get(userId="me", id=message_id, format="full").execute()), gmail=gmail)


class MessageDraft:
    """A class representing a message that doesn't yet exist. All public methods allow chaining. At the end of the method chain call FluentMessage.send() to send the message."""

    def __init__(self, gmail: Gmail, parent: Message = None) -> None:
        self.gmail, self.parent = gmail, parent
        self.mime = MIMEMultipart()
        self._attachment = None  # type: str

    def subject(self, subject: str) -> MessageDraft:
        """Set the subject of the message."""
        self.mime["Subject"] = subject
        return self

    def body(self, body: str) -> MessageDraft:
        """Set the body of the message. The body should be an html string, but python newline and tab characters will be automatically converted to their html equivalents."""
        self.mime.attach(MIMEText(body))
        return self

    def from_(self, address: str) -> MessageDraft:
        """Set the email address this message will appear to originate from."""
        self.mime["From"] = address
        return self

    def to(self, contacts: Union[str, Collection[str]]) -> MessageDraft:
        """Set the email address(es) (a single one or a collection of them) this message will be sent to. Email addresses can be provided either as strings or as contact objects."""
        self.mime["To"] = self._parse_contacts(contacts=contacts)
        return self

    def cc(self, contacts: Union[str, Collection[str]]) -> MessageDraft:
        """Set the email address(es) (a single one or a collection of them) this message will be sent to. Email addresses can be provided either as strings or as contact objects."""
        self.mime["Cc"] = self._parse_contacts(contacts=contacts)
        return self

    def attach(self, attachments: Union[PathLike, Collection[PathLike]]) -> MessageDraft:
        """Attach a file or a collection of files to this message."""
        for attachment in ([attachments] if isinstance(attachments, (str, os.PathLike)) else attachments):
            self._attach_file(attachment)
        return self

    def send(self) -> bool:
        """Send this message as it currently is."""
        body = {"raw": base64.urlsafe_b64encode(self.mime.as_bytes()).decode()}
        if self.parent is not None:
            body["threadId"] = self.parent.thread_id

        message_id = Dict_(self.gmail.service.users().messages().send(userId="me", body=body).execute()).id
        return Message.from_id(message_id=message_id, gmail=self.gmail)

    def _parse_contacts(self, contacts: Union[str, Collection[str]]) -> List[str]:
        return ", ".join(contacts) if is_non_string_iterable(contacts) else contacts

    def _attach_file(self, path: PathLike) -> None:
        file = File.from_pathlike(path)
        attachment = MIMEApplication(file.path.read_bytes(), _subtype=file.extension)
        attachment.add_header("Content-Disposition", "attachment", filename=file.name)
        self.mime.attach(attachment)
