from __future__ import annotations

import os
from typing import Union, Collection, TYPE_CHECKING, Optional
from html import escape, unescape

import emails

from subtypes import Html, Str
from pathmagic import File, PathLike
from miscutils import OneOrMany, Base64

if TYPE_CHECKING:
    from .gmail import Gmail
    from .message import Message, Contact


class MessageDraft:
    """A class representing a message that doesn't yet exist. All public methods allow chaining. At the end of the method chain call FluentMessage.send() to send the message."""

    def __init__(self, gmail: Gmail, parent: Message = None) -> None:
        self.gmail, self.parent = gmail, parent
        self._subject = self._html = self._text = self._from = self._to = self._cc = self._bcc = None  # type: Optional[str]
        self._attachments: list[File] = []

    def subject(self, subject: str) -> MessageDraft:
        """Set the subject of the message."""
        self._subject = subject
        return self

    def html(self, html: str) -> MessageDraft:
        """Set the html body of the message. This should be valid html string, though special html characters will be escaped. If no text is provided, it will be generated from this html by stripping away all tags, unescaping, andconverting html whitespace characters to utf-8."""
        self._html = html
        return self

    def text(self, text: str) -> MessageDraft:
        """Set the text body of the message. If no html body is provided, it will be generated from this text, with python whitespace characters automatically converted to their html equivalents."""
        self._text = text
        return self

    def from_(self, address: str) -> MessageDraft:
        """Set the email address this message will appear to originate from."""
        self._from = address
        return self

    def to(self, contacts: Union[Union[Contact, str], Collection[Union[Contact, str]]]) -> MessageDraft:
        """Set the email address(es) (a single one or a collection of them) this message will be sent to. Email addresses can be provided either as strings or as contact objects."""
        self._to = self._parse_contacts(contacts=contacts)
        return self

    def cc(self, contacts: Union[Union[Contact, str], Collection[Union[Contact, str]]]) -> MessageDraft:
        """Set the email address(es) (a single one or a collection of them) this message will be CCd to. Email addresses can be provided either as strings or as contact objects."""
        self._cc = self._parse_contacts(contacts=contacts)
        return self

    def bcc(self, contacts: Union[Union[Contact, str], Collection[Union[Contact, str]]]) -> MessageDraft:
        """Set the email address(es) (a single one or a collection of them) this message will be BCCd to. Email addresses can be provided either as strings or as contact objects."""
        self._bcc = self._parse_contacts(contacts=contacts)
        return self

    def attach(self, attachments: Union[PathLike, Collection[PathLike]]) -> MessageDraft:
        """Attach a file or a collection of files to this message."""
        self._attachments += [File.from_pathlike(file) for file in OneOrMany(of_type=(str, os.PathLike)).to_list(attachments)]
        return self

    def send(self) -> bool:
        """Send this message as it currently is."""
        message_id = self.gmail.service.users().messages().send(userId="me", body=self._prepare_message_body()).execute()["id"]
        return self.gmail.Constructors.Message.from_id(message_id=message_id, gmail=self.gmail)

    def _prepare_message_body(self) -> dict:
        html = plain = None  # type: Optional[str]

        if self._html:
            html = self._html
            if not self._text:
                plain = self._html_to_plaintext(self._html)

        if self._text:
            plain = self._text
            if not self._html:
                html = f"<pre>{escape(self._text)}</pre>"

        msg = emails.Message(subject=self._subject, mail_from=self._from, mail_to=self._to, html=html, text=plain, cc=self._cc, bcc=self._bcc, headers=None, charset="utf-8")
        for attachment in self._attachments:
            msg.attach(filename=attachment.name, data=attachment.path.read_bytes())

        body = {"raw": Base64(raw_bytes=msg.build_message().as_bytes()).to_b64()}

        if self.parent is not None:
            body["threadId"] = self.parent.thread_id

        return body

    def _parse_contacts(self, contacts: Union[str, Collection[str]]) -> list[str]:
        return [str(contact) for contact in OneOrMany(of_type=(self.gmail.Constructors.Contact, str)).to_list(contacts)]

    def _html_to_plaintext(self, html: str) -> str:
        markup = Html(unescape(self._html.replace("<br>", "\n")))
        for meta in ["base", "head", "link", "meta", "style", "title"]:
            for tag in markup.find_all(meta):
                tag.extract()

        return Str(markup.text).trim.whitespace_runs(newlines=2)
