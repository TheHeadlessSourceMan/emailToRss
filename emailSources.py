"""
General interface and implementations for email sources.
"""
import typing
import email
import imaplib
import mailbox
import os
from email.header import decode_header
from email.message import Message
from .feedStore import FeedStore
from .settings import Settings


class EmailSource:
    """
    Base class for something that can be polled for tagged messages.
    """

    def __init__(self,store:FeedStore):
        """
        :store: where to put discovered items
        """
        self.store=store

    def poll(self)->bool:
        """
        Check for new tagged messages.

        :return: True if any new items were added
        """
        raise NotImplementedError()


class ImapEmailSource(EmailSource):
    """
    Reads tagged messages from an IMAP server.
    """

    def __init__(self,settings:Settings,store:FeedStore):
        """
        :settings: source config with host, username, password,
            and optionally port and folder
        """
        EmailSource.__init__(self,store)
        self.settings=settings

    def poll(self)->bool:
        """
        Fetch RSS and RSS+DEL tagged messages, deleting the latter.
        """
        conn=imaplib.IMAP4_SSL(
            self.settings['host'],self.settings.get('port',993))
        conn.login(self.settings['username'],self.settings['password'])
        conn.select(self.settings.get('folder','INBOX'))
        ids:typing.Set[bytes]=set()
        dels:typing.Set[bytes]=set()
        for tag in ('RSS','RSS+DEL'):
            _,data=conn.uid('SEARCH','KEYWORD',tag)
            if data and data[0]:
                found=set(data[0].split())
                ids|=found
                if tag=='RSS+DEL':
                    dels|=found
        changed=False
        for uid in ids:
            _,msgData=conn.uid('FETCH',uid.decode(),'(RFC822)')
            msg=email.message_from_bytes(msgData[0][1])
            guid=msg.get('Message-ID',uid.decode())
            subject=decodeHeader(msg.get('Subject',''))
            if self.store.add(guid,subject,getBody(msg)):
                changed=True
            if uid in dels:
                conn.uid('STORE',uid.decode(),'+FLAGS','(\\Deleted)')
        if dels:
            conn.expunge()
        conn.logout()
        return changed


class LocalEmailSource(EmailSource):
    """
    Reads tagged messages from a local mbox file or Maildir.
    """

    def __init__(self,settings:Settings,store:FeedStore):
        """
        :settings: source config with path
        """
        EmailSource.__init__(self,store)
        self.path:str=settings['path']

    def poll(self)->bool:
        """
        Read RSS and RSS+DEL tagged messages, removing the latter.
        """
        changed=False
        box:mailbox.Mailbox
        if os.path.isdir(os.path.join(self.path,'cur')):
            box=mailbox.Maildir(self.path,create=False)
        else:
            box=mailbox.mbox(self.path)
        remove:typing.List[str]=[]
        for key,msg in box.items():
            msgTags=getTags(msg)
            if 'RSS' in msgTags or 'RSS+DEL' in msgTags:
                guid=msg.get('Message-ID',str(key))
                subject=decodeHeader(msg.get('Subject',''))
                if self.store.add(guid,subject,getBody(msg)):
                    changed=True
                if 'RSS+DEL' in msgTags:
                    remove.append(key)
        for key in remove:
            box.remove(key)
        box.flush()
        return changed


def getEmailSources(
    settings:Settings,
    store:FeedStore
    )->typing.Iterable[EmailSource]:
    """
    Create a list of email source instances based on the configuration.
    """
    sources:typing.List[EmailSource]=[]
    for sourcesettings in settings['sources']:
        if sourcesettings['type']=='imap':
            sources.append(ImapEmailSource(sourcesettings,store))
        else:
            sources.append(LocalEmailSource(sourcesettings,store))
    return sources


def decodeHeader(value:typing.Optional[str])->str:
    """
    Decode a possibly-encoded mail header into plain text.
    """
    out:typing.List[str]=[]
    for part,encoding in decode_header(value or ''):
        if isinstance(part,bytes):
            out.append(part.decode(encoding or 'utf-8','replace'))
        else:
            out.append(part)
    return ''.join(out)


def getBody(msg:Message)->str:
    """
    Get the first text/plain body of a message, or '' if there is none.
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type()=='text/plain':
                data=part.get_payload(decode=True)
                if isinstance(data,bytes) and data:
                    return data.decode(errors='replace')
    else:
        data=msg.get_payload(decode=True)
        if isinstance(data,bytes) and data:
            return data.decode(errors='replace')
    return ''


def getTags(msg:Message)->typing.Set[str]:
    """
    Get the Thunderbird tags (X-Mozilla-Keys) of a message.
    """
    return set(str(msg.get('X-Mozilla-Keys','')).split())
