from __future__ import annotations

import webbrowser

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from pathmagic import File
from iotools import Config, Gui, Widget

from .label import BaseLabel, Label, UserLabel, SystemLabel, Category, LabelAccessor
from .message import Message, MessageDraft, Contact, Body, Attachments, Attachment
from .query import Query
import gmailapi


class Gmail:
    class Constructors:
        Label, UserLabel, SystemLabel, Category = Label, UserLabel, SystemLabel, Category
        Message, MessageDraft, Query = Message, MessageDraft, Query
        Contact, Body, Attachments, Attachment = Contact, Body, Attachments, Attachment

    BATCH_SIZE = 100
    BATCH_DELAY_SECONDS = 1

    DEFAULT_SCOPES = ["https://mail.google.com/"]
    ALL_SCOPES = [
        "https://www.googleapis.com/auth/gmail.labels",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.insert",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.metadata",
        "https://www.googleapis.com/auth/gmail.settings.basic",
        "https://www.googleapis.com/auth/gmail.settings.sharing",
        "https://mail.google.com/",
    ]

    def __init__(self) -> None:
        self.config = Config(name=gmailapi.__name__)

        self.token = self.config.dir.new_dir("tokens").new_file("token", "pkl")
        self.credentials = self.token.read()
        self._ensure_credentials_are_valid()

        self.service = build("gmail", "v1", credentials=self.credentials)
        self.address = self.service.users().getProfile(userId="me").execute()["emailAddress"]

        self.labels = LabelAccessor(gmail=self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(address={repr(self.address)})"

    def __getitem__(self, val: str) -> BaseLabel:
        return self.label_from_name(val)

    @property
    def draft(self) -> MessageDraft:
        return self.Constructors.MessageDraft(gmail=self)

    @property
    def messages(self) -> Query:
        return self.Constructors.Query(gmail=self)

    def create_label(self, name: str, label_list_visibility: str = "labelShow", message_list_visibility: set = "show",
                     text_color: str = None, background_color: str = None) -> UserLabel:
        return self.Constructors.UserLabel.create(name=name, label_list_visibility=label_list_visibility, message_list_visibility=message_list_visibility,
                                                  text_color=text_color, background_color=background_color, gmail=self)

    def label_from_name(self, label_name: str) -> BaseLabel:
        return self.labels._registry.get_by_name(label_name).entity

    def _refresh_labels(self):
        self.labels._refresh()

    def _ensure_credentials_are_valid(self) -> None:
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
            self.token.write(self.credentials)

        if not self.credentials or not self.credentials.valid:
            print("Before continuing, please create a new Gmail API project with OAuth 2.0 credentials, or download your credentials from an existing project.")
            webbrowser.open("https://console.developers.google.com/")
            self.credentials = InstalledAppFlow.from_client_secrets_file(str(self._request_credentials_json()), self.DEFAULT_SCOPES).run_local_server(port=0)
            self.token.content = self.credentials

    def _request_credentials_json(self) -> File:
        with Gui(name="gmail", on_close=lambda: None) as gui:
            Widget.Label("Please provide a client secrets JSON file...").stack()
            file_select = Widget.FileSelect().stack()
            Widget.Button(text="Continue", command=gui.end).stack()

        gui.start()
        return file_select.state
