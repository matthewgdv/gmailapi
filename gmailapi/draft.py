from __future__ import annotations

import os
from typing import List, Union, Collection, TYPE_CHECKING
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from pathmagic import File, PathLike
from subtypes import Dict_
from miscutils import is_non_string_iterable

if TYPE_CHECKING:
    from .gmail import Gmail
    from .message import Message


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
        self.mime["From"] = str(address)
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
        return ", ".join([str(contact) for contact in contacts]) if is_non_string_iterable(contacts) else str(contacts)

    def _attach_file(self, path: PathLike) -> None:
        file = File.from_pathlike(path)
        attachment = MIMEApplication(file.path.read_bytes(), _subtype=file.extension)
        attachment.add_header("Content-Disposition", "attachment", filename=file.name)
        self.mime.attach(attachment)
