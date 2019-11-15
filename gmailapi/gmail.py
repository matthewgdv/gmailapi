from __future__ import annotations

import time
from typing import List, Union
import webbrowser

from googleapiclient.discovery import build, BatchHttpRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from pathmagic import File
from subtypes import Dict_
from miscutils import OneOrMany
from iotools import Config, Gui, widget

from .proxy import SystemDefaults, LabelAccessor
from .label import BaseLabel, Label, UserLabel, SystemLabel, Category
from .message import Message, MessageDraft
import gmailapi


class Config(Config):
    app_name = gmailapi.__name__


class Gmail:
    class Constructors:
        BaseLabel, Label, UserLabel, SystemLabel, Category = BaseLabel, Label, UserLabel, SystemLabel, Category
        Message, MessageDraft = Message, MessageDraft

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

        self.system = SystemDefaults(gmail=self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(address={repr(self.address)})"

    def __getitem__(self, val: str) -> BaseLabel:
        return self.label_from_name(val)

    @property
    def draft(self) -> MessageDraft:
        return self.Constructors.MessageDraft(gmail=self)

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
            return [self.Constructors.Message.from_id(message_id=message_id, gmail=self) for message_id in message_ids]
        else:
            return sum([self._fetch_messages_in_batch(message_ids[index:index + batch_size], batch_delay=batch_delay) for index in range(0, len(message_ids), batch_size)], [])

    def create_label(self, name: str, label_list_visibility: str = "labelShow", message_list_visibility: set = "show", text_color: str = None, background_color: str = None) -> UserLabel:
        return self.Constructors.UserLabel.create(name=name, label_list_visibility=label_list_visibility, message_list_visibility=message_list_visibility, text_color=text_color, background_color=background_color, gmail=self)

    def label_from_name(self, label_name: str) -> BaseLabel:
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

        return [self.Constructors.Message(resource=resource, gmail=self) for resource in resources]
