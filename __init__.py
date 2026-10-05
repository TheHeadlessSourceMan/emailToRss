"""
Email to RSS Bridge

Features
- Reads tagged messages from IMAP
  and/or local Thunderbird mbox/Maildir stores.
- Tags supported:
    RSS      -> publish to feed, keep message.
    RSS+DEL  -> publish to feed, then delete message.
- Stores feed items in SQLite.
- Prevents duplicates using message GUID tracking.
- Serves RSS over HTTP using only the python standard library.
- Uses atomic snapshot replacement for race-free feed serving.

Configuration: data/settings.yaml
"""
from .emailSources import *
from .emailToRssServer import *
from .feedState import *
from .feedStore import *
from .rssServer import *
from .settings import *
