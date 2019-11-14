from __future__ import annotations

import os
import time
from typing import List, Union, Collection
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import webbrowser

from googleapiclient.discovery import build, BatchHttpRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from maybe import Maybe
from pathmagic import File, Dir, PathLike
from subtypes import Dict_, DateTime, NameSpace, Str, Markup
from miscutils import is_non_string_iterable, lazy_property, OneOrMany
from iotools import Config, Gui, HtmlGui
import iotools.widget as widget


class Config(Config):
    app_name = "gmail"


class Gmail:
    DEFAULT_SCOPES = ["https://mail.google.com/"]
    ALL_SCOPES = [
        "https://www.googleapis.com/auth/gmail.labels"
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.insert",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.metadata",
        "https://www.googleapis.com/auth/gmail.settings.basic",
        "https://www.googleapis.com/auth/gmail.settings.sharing",
        "https://mail.google.com/"
    ]

    def __init__(self) -> None:
        self.config = Config()

        self.token = self.config.appdata.new_dir("tokens").new_file("token", "pkl")
        self.credentials = self.token.contents
        self._ensure_credentials_are_valid()

        self.service = build('gmail', 'v1', credentials=self.credentials)
        self.address = Dict_(self.service.users().getProfile(userId="me").execute()).emailAddress

        self.labels = LabelAccessor(gmail=self)
        self.labels._regenerate_label_tree()

        self.default = SystemDefaults(gmail=self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(address={repr(self.address)})"

    def __getitem__(self, val: str) -> Label:
        return self.label_from_name(val)

    @property
    def message(self) -> FluentMessage:
        return FluentMessage(gmail=self)

    def messages(self, query: str = None, labels: Union[BaseLabel, List[BaseLabel]] = None, limit: int = 50, include_trash: bool = False, batch_size: int = 50, batch_delay: int = 1) -> List[Message]:
        label_ids = None if labels is None else [label.id for label in OneOrMany(of_type=BaseLabel).to_list(labels)]
        kwargs = {key: val for key, val in {"q": query, "labelIds": label_ids, "maxResults": limit, "includeSpamTrash": include_trash}.items() if val is not None}

        response = Dict_(self.service.users().messages().list(userId="me", **kwargs).execute())
        resources = response.get("messages", [])

        kwargs["maxResults"] = 500 if limit is None else limit - len(resources)
        while kwargs["maxResults"] > 0 and "nextPageToken" in response:
            response = Dict_(self.service.users().messages().list(userId="me", pageToken=response.nextPageToken, **kwargs).execute())
            resources += response.messages

            kwargs["maxResults"] = 500 if limit is None else limit - len(resources)

        message_ids = [resouce.id for resouce in resources]
        if batch_size is None:
            return [Message.from_id(message_id=message_id, gmail=self) for message_id in message_ids]
        else:
            return sum([self._fetch_messages_in_batch(message_ids[index:index + batch_size], batch_delay=batch_delay) for index in range(0, len(message_ids), batch_size)], [])

    def create_label(self, name: str, label_list_visibility: str = "labelShow", message_list_visibility: set = "show", text_color: str = None, background_color: str = None) -> Label:
        label = {"name": name, "labelListVisibility": label_list_visibility, "messageListVisibility": message_list_visibility}

        if text_color or background_color:
            color = {name: val for name, val in {"textColor": text_color, "backgroundColor": background_color}.items() if val is not None}
            if color:
                label["color"] = color

        label = Label(label_id=self.service.users().labels().create(userId="me", body=label).execute()["id"], gmail=self)
        self.labels._regenerate_label_tree()
        return label

    def label_from_name(self, label_name: str) -> Label:
        return self.labels._name_mappings_[label_name]()

    def expire(self) -> Gmail:
        for proxy in self.labels._id_mappings_.values():
            proxy._entity_ = None
        return self

    def _ensure_credentials_are_valid(self) -> None:
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
            self.token.contents = self.credentials

        if not self.credentials or not self.credentials.valid:
            print("Before continuing, please create a new project with OAuth 2.0 credentials, or download your credentials from an existing project.")
            webbrowser.open("https://console.developers.google.com/")
            self.credentials = InstalledAppFlow.from_client_secrets_file(self._request_credentials_json(), self.DEFAULT_SCOPES).run_local_server(port=0)
            self.token.contents = self.credentials

    def _request_credentials_json(self) -> File:
        with Gui(name="gmail", on_close=lambda: None) as gui:
            widget.Label("Please provide a 'credentials.json' file...").stack()
            file_select = widget.FileSelect().stack()
            widget.Button(text="Continue", command=gui.end).stack()

        gui.start()
        return file_select.state

    def _fetch_messages_in_batch(self, message_ids: List[str], batch_delay: int = 1) -> List[Message]:
        def append_to_list(response_id: str, response: dict, exception: Exception) -> None:
            if exception is not None:
                raise exception

            resources.append(Dict_(response))

        resources, batch = [], BatchHttpRequest(callback=append_to_list)
        for message_id in message_ids:
            batch.add(self.service.users().messages().get(userId="me", id=message_id))

        batch.execute()
        time.sleep(batch_delay)

        return [Message(resource=resource, gmail=self) for resource in resources]


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

    @lazy_property
    def labels(self) -> SystemLabels:
        return SystemLabels(gmail=self._gmail)

    @lazy_property
    def categories(self) -> SystemCategories:
        return SystemCategories(gmail=self._gmail)


class LabelAccessor(NameSpace):
    def __init__(self, gmail: Gmail) -> None:
        self._gmail_, self._id_mappings_, self._name_mappings_ = gmail, {}, {}

    def _regenerate_label_tree(self) -> LabelAccessor:
        self._gmail_.expire(), self._clear()

        labels = Dict_(self._gmail_.service.users().labels().list(userId="me").execute()).labels
        real_labels = [label for label in labels if label.id not in SystemCategories._id_name_mappings]

        existing_label_ids = {label.id for label in real_labels}
        for label_id, proxy in self._id_mappings_.items():
            if label_id not in existing_label_ids:
                self._id_mappings_.pop(label_id), self._name_mappings_.pop(proxy._entity_name_)

        for label in real_labels:
            if label.id in SystemLabels._id_name_mappings:
                label.name = SystemLabels._id_name_mappings[label.id]

            node, iterable = self, label.name.split('/') or [label.name]
            for index, level in enumerate(iterable):
                if level:
                    if level in node:
                        node = node[level]
                    else:
                        if label.id in self._id_mappings_:
                            proxy = self._id_mappings_[label.id]
                            proxy._entity_name_, proxy._parent_ = label.name, node if node is not self else None
                            proxy._clear()
                        else:
                            proxy = LabelProxy(entity_id=label.id, entity_name=label.name, gmail=self._gmail_, parent=node if node is not self else None)

                        stem = level if index + 1 == len(iterable) else "/".join(iterable[index:])
                        node[stem] = proxy
                        break

        return self


class BaseProxy(NameSpace):
    def __init__(self, entity_id: str, entity_name: str, gmail: str, parent: LabelProxy = None) -> None:
        self._entity_id_, self._entity_name_, self._gmail_, self._parent_ = entity_id, entity_name, gmail, parent
        self._entity_: BaseLabel = None
        self._gmail_.labels._id_mappings_[entity_id] = self._gmail_.labels._name_mappings_[entity_name] = self

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join([f'{repr(self._entity_name_)}', *[f'{attr}={repr(val)}' for attr, val in self]])})"


class LabelProxy(BaseProxy):
    def __call__(self) -> Label:
        if self._entity_ is None:
            self._entity_ = (SystemLabel if self._entity_id_ in SystemLabels._id_name_mappings else UserLabel)(label_id=self._entity_id_, gmail=self._gmail_)

        return self._entity_


class CategoryProxy(BaseProxy):
    def __call__(self) -> Category:
        if self._entity_ is None:
            self._entity_ = Category(label_id=self._entity_id_, gmail=self._gmail_)

        return self._entity_


class BaseLabel:
    def __init__(self, label_id: str, gmail: Gmail) -> None:
        self.id, self.gmail = label_id, gmail
        self.refresh()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={repr(self.name)}, type={repr(self.type)}, messages_total={repr(self.messages_total)}, messages_unread={repr(self.messages_unread)})"

    def __str__(self) -> str:
        return self.name

    def __call__(self) -> BaseLabel:
        return self.refresh()

    def __contains__(self, other: Union[BaseLabel, Message]) -> bool:
        if isinstance(other, BaseLabel):
            return other.name in self.name
        elif isinstance(other, Message):
            return self in other.labels or self == other.category
        else:
            raise TypeError(f"Cannot test '{type(other).__name__}' object for membership in a '{type(self).__name__}' object. Must be type '{BaseLabel.__name__}' or '{Message.__name__}'.")

    def __hash__(self) -> int:
        return hash(self.id)

    def __getitem__(self, name: str) -> BaseLabel:
        return self.gmail.labels._id_mappings_[self.id][name]()

    @property
    def parent(self) -> BaseLabel:
        return self.gmail.labels._id_mappings_[self.id]._parent_()

    @property
    def children(self) -> List[BaseLabel]:
        return [label() for name, label in self.gmail.labels._id_mappings_[self.id]]

    def create_child_label(self, name: str, label_list_visibility: str = "labelShow", message_list_visibility: set = "show", text_color: str = None, background_color: str = None) -> BaseLabel:
        return self.gmail.create_label(name=f"{self.name}/{name}", label_list_visibility=label_list_visibility, message_list_visibility=message_list_visibility, text_color=text_color, background_color=background_color)

    def messages(self, query: str = None, limit: int = 25, include_trash: bool = False, batch_size: int = 50) -> List[Message]:
        return self.gmail.messages(query=query, limit=limit, labels=self, include_trash=include_trash, batch_size=batch_size)

    def refresh(self) -> BaseLabel:
        self.resource = Dict_(self.gmail.service.users().labels().get(userId="me", id=self.id).execute())

        self.id, self.name, self.type = self.resource.id, self.resource.name, self.resource.get("type", "user")
        self.messages_total, self.messages_unread = self.resource.messagesTotal, self.resource.messagesUnread
        self.threads_total, self.threads_unread = self.resource.threadsTotal, self.resource.threadsUnread
        self.message_list_visibility, self.label_list_visibility = self.resource.get("messageListVisibility"), self.resource.get("labelListVisibility")
        return self


class Label(BaseLabel):
    pass


class UserLabel(Label):
    def update(self, name: str = None, label_list_visibility: str = None, message_list_visibility: set = None, text_color: str = None, background_color: str = None) -> BaseLabel:
        color = {name: val for name, val in {"textColor": text_color, "backgroundColor": background_color}.items() if val is not None} if text_color or background_color else None
        body = {name: val for name, val in {"name": name, "labelListVisibility": label_list_visibility, "messageListVisibility": message_list_visibility, "color": color}.items() if val is not None}

        if not body:
            raise RuntimeError(f"Cannot call {type(self).__name__}.{self.update.__name__} without arguments.")
        else:
            body["id"] = self.id
            self.gmail.service.users().labels().update(userId="me", id=self.id, body=body).execute()
            self.refresh()
            self.gmail.labels._regenerate_label_tree()

        return self

    def delete(self, recursive: bool = False) -> None:
        self.gmail.service.users().labels().delete(userId="me", id=self.id).execute()

        if recursive:
            for label in Dict_(self.gmail.service.users().labels().list(userId="me").execute()).labels:
                if label.name.startswith(f"{self.name}/") and label.type == "user":
                    self.gmail.service.users().labels().delete(userId="me", id=label.id).execute()

        self.gmail.labels._regenerate_label_tree()


class SystemLabel(Label):
    def refresh(self) -> BaseLabel:
        super().refresh()
        self.name = SystemLabels._id_name_mappings[self.id]


class Category(BaseLabel):
    def refresh(self) -> BaseLabel:
        super().refresh()
        self.name = SystemCategories._id_name_mappings[self.id]


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

    def __contains__(self, other: Label) -> bool:
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
        if isinstance(category, Category):
            self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"removeLabelIds": self.category.id, "addLabelIds": category.id}).execute()
            self.refresh()
        else:
            raise TypeError(f"Argument to '{self.change_category_to.__name__}' must be of type '{Category.__name__}', not '{type(category).__name__}'.")

        return self

    def add_labels(self, labels: Union[Label, Collection[Label]]) -> Message:
        self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"addLabelIds": OneOrMany(of_type=Label).to_list(labels)}).execute()
        self.refresh()
        return self

    def remove_labels(self, labels: Union[Label, Collection[Label]]) -> Message:
        self.gmail.service.users().messages().modify(userId="me", id=self.id, body={"removeLabelIds": OneOrMany(of_type=Label).to_list(labels)}).execute()
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

    def reply(self) -> FluentMessage:
        return FluentMessage(gmail=self.gmail, parent=self).to(self.from_).subject(f"RE: {self.subject}")

    def forward(self) -> FluentMessage:
        return FluentMessage(gmail=self.gmail, parent=self).subject(f"FWD: {self.subject}")

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
        self.labels = {label for label in all_labels if isinstance(label, Label)}
        self.category = OneOrMany(of_type=Category).to_one_or_none([label for label in all_labels if isinstance(label, Category)])

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


class FluentMessage:
    """A class representing a message that doesn't yet exist. All public methods allow chaining. At the end of the method chain call FluentMessage.send() to send the message."""

    def __init__(self, gmail: Gmail, parent: Message = None) -> None:
        self.gmail, self.parent = gmail, parent
        self.mime = MIMEMultipart()
        self._attachment = None  # type: str

    def subject(self, subject: str) -> FluentMessage:
        """Set the subject of the message."""
        self.mime["Subject"] = subject
        return self

    def body(self, body: str) -> FluentMessage:
        """Set the body of the message. The body should be an html string, but python newline and tab characters will be automatically converted to their html equivalents."""
        self.mime.attach(MIMEText(body))
        return self

    def from_(self, address: str) -> FluentMessage:
        """Set the email address this message will appear to originate from."""
        self.mime["From"] = address
        return self

    def to(self, contacts: Union[str, Collection[str]]) -> FluentMessage:
        """Set the email address(es) (a single one or a collection of them) this message will be sent to. Email addresses can be provided either as strings or as contact objects."""
        self.mime["To"] = self._parse_contacts(contacts=contacts)
        return self

    def cc(self, contacts: Union[str, Collection[str]]) -> FluentMessage:
        """Set the email address(es) (a single one or a collection of them) this message will be sent to. Email addresses can be provided either as strings or as contact objects."""
        self.mime["Cc"] = self._parse_contacts(contacts=contacts)
        return self

    def attach(self, attachments: Union[PathLike, Collection[PathLike]]) -> FluentMessage:
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
