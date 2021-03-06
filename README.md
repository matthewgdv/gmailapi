PLEASE NOTE:
====================

This library is currently still under development. The API will likely undergo significant changes that may break any code you write with it.
The documentation will fall out of sync with the updates regularly until development slows down. Use it at your own risk.

Overview
====================

A library providing Python bindings for the Gmail api.

The `Gmail` class
--------------------

* Central handler class
* Will run through an interactive webserver for granting delegated authentication if no Oauth token is preconfigured
* `Gmail.draft` allows for writing new emails using an intuitive fluent-design syntax using the `MessageDraft` class
* Allows creation/deletion of new user labels and nested labels
* Creates the entire hierarchy of labels on-the-fly as `Gmail.labels`, such that labels (including nested labels) can be accessed using attribute access (e.g. `Gmail().labels.inbox.some_nested_label()`) 
* Complex message queries can be written using the `Query` class accessible as `Gmail.messages` in conjunction with the various `Message.Attributes` objects 
* Labels and categories are fully featured API objects and `Query` objects can be started on them rather than on `Gmail` to limit the resultset of message queries 
  

Installation
====================

To install use pip:

    $ pip install gmailapi


Or clone the repo:

    $ git clone https://github.com/matthewgdv/gmailapi.git
    $ python setup.py install


Usage
====================

Usage coming soon...

Contributing
====================

Contributions are welcome, and they are greatly appreciated! Every little bit helps, and credit will always be given.

You can contribute in many ways:

Report Bugs
--------------------

Report bugs at https://github.com/matthewgdv/gmailapi/issues

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
--------------------

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help wanted" is open to whoever wants to implement a fix for it.

Implement Features
--------------------

Look through the GitHub issues for features. Anything tagged with "enhancement" and "help wanted" is open to whoever wants to implement it.

Write Documentation
--------------------

The repository could always use more documentation, whether as part of the official docs, in docstrings, or even on the web in blog posts, articles, and such.

Submit Feedback
--------------------

The best way to send feedback is to file an issue at https://github.com/matthewgdv/office/issues.

If you are proposing a new feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions are welcome :)

Get Started!
--------------------

Before you submit a pull request, check that it meets these guidelines:

1.  If the pull request adds functionality, it should include tests and the docs should be updated. Write docstrings for any functions that are part of the external API, and add
    the feature to the README.md.

2.  If the pull request fixes a bug, tests should be added proving that the bug has been fixed. However, no update to the docs is necessary for bugfixes.

3.  The pull request should work for the newest version of Python (currently 3.7). Older versions may incidentally work, but are not officially supported.

4.  Inline type hints should be used, with an emphasis on ensuring that introspection and autocompletion tools such as Jedi are able to understand the code wherever possible.

5.  PEP8 guidelines should be followed where possible, but deviations from it where it makes sense and improves legibility are encouraged. The following PEP8 error codes can be
    safely ignored: E121, E123, E126, E226, E24, E704, W503

6.  This repository intentionally disallows the PEP8 79-character limit. Therefore, any contributions adhering to this convention will be rejected. As a rule of thumb you should
    endeavor to stay under 200 characters except where going over preserves alignment, or where the line is mostly non-algorythmic code, such as extremely long strings or function
    calls.
