"""
General interface and implementations for email sources.
"""
from pathlib import Path
import typing
import configparser
import email
import imaplib
import json
import mailbox
import os
import re
from email.header import decode_header
from email.message import Message
from feedStore import FeedStore
from settings import Settings


class EmailSource:
    """
    Base class for something that can be polled for tagged messages.
    """

    def __init__(self,store:FeedStore):
        """
        :store: where to put discovered items
        """
        self.store=store

    @property
    def name(self)->str:
        """
        Get a name for this source
        """
        raise NotImplementedError()

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

    @property
    def email(self)->str:
        """
        Get email address of this account
        """
        return f"{self.settings['user']}@{self.settings['host']}"
    
    @property
    def name(self)->str:
        return f"IMAP: {self.email}"

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
    Reads tagged messages from a local mbox file or maildir.
    """

    def __init__(self,settings:Settings,store:FeedStore):
        """
        :settings: source config with path
        """
        EmailSource.__init__(self,store)
        self.path:str=settings['path']

    @property
    def name(self)->str:
        """
        Name of this account
        """
        return str(self.path)

    def poll(self)->bool:
        """
        Read RSS and RSS+DEL tagged messages, removing the latter.
        """
        changed=False
        path=Path(self.path)
        box:typing.Union[mailbox.Maildir,mailbox.mbox]
        if isMaildir(path):
            box=mailbox.Maildir(str(path),create=False)
        elif path.is_file():
            box=mailbox.mbox(str(path),create=False)
        else:
            return False
        # mbox must be locked while Thunderbird may also be writing it
        box.lock()
        try:
            remove:typing.List[str]=[]
            for key,msg in box.items():
                msgTags=getTags(msg)
                if 'RSS' in msgTags or 'RSS+DEL' in msgTags:
                    guid=msg.get('Message-ID',f'{path}:{key}')
                    subject=decodeHeader(msg.get('Subject',''))
                    if self.store.add(guid,subject,getBody(msg)):
                        changed=True
                    if 'RSS+DEL' in msgTags:
                        remove.append(key)
            for key in remove:
                box.remove(key)
            if remove:
                box.flush()
        finally:
            box.unlock()
            box.close()
        return changed


def getEmailSources(
    settings:Settings,
    store:FeedStore,
    autodetectLocalSources:typing.Optional[bool]=None
    )->typing.Iterable[EmailSource]:
    """
    Create a list of email source instances based on the configuration.
    """
    if autodetectLocalSources is None:
        autodetectLocalSources=settings.get("autodetectLocalSources",True)
    sources:typing.List[EmailSource]=[]
    for sourcesettings in settings.get('sources',[]):
        if sourcesettings['type']=='imap':
            sources.append(ImapEmailSource(sourcesettings,store))
        else:
            sources.append(LocalEmailSource(sourcesettings,store))
    if autodetectLocalSources:
        findLocalMailSources(store,ignore=sources)
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


_NOT_MAILBOX_SUFFIXES=('.msf','.dat','.json','.html','.txt','.lock','.sqlite')


def isMaildir(path:Path)->bool:
    """
    True if path is a Maildir (has cur and new subdirectories).
    """
    return (path/'cur').is_dir() and (path/'new').is_dir()


def isMbox(path:Path)->bool:
    """
    True if path looks like an mbox file: it starts with a 'From ' line,
    or it is an (empty) Thunderbird folder with an .msf index beside it.
    """
    if not path.is_file() or path.suffix.lower() in _NOT_MAILBOX_SUFFIXES:
        return False
    if path.with_name(path.name+'.msf').exists():
        return True
    try:
        with open(path,'rb') as f:
            return f.read(5)==b'From '
    except OSError:
        return False


def scanForMailboxes(root:Path,maxDepth:int=8)->typing.Iterable[Path]:
    """
    Recursively find every Maildir directory and mbox file under root
    (including root itself). Covers Thunderbird/Betterbird .sbd subfolder
    directories and Maildir++ dot-folders.
    """
    try:
        if isMaildir(root):
            yield root
            children=[c for c in sorted(root.iterdir())
                if c.name not in ('cur','new','tmp')]
        elif root.is_dir():
            children=sorted(root.iterdir())
        else:
            if isMbox(root):
                yield root
            return
    except OSError:
        return
    if maxDepth<=0:
        return
    for child in children:
        if child.is_symlink() and child.is_dir():
            continue
        yield from scanForMailboxes(child,maxDepth-1)


_PREF_RE=re.compile(
    r'user_pref\("(mail\.(?:server\.server\d+\.directory'
    r'|root\.(?:none|imap|pop3|nntp)))(-rel)?",\s*"((?:[^"\\]|\\.)*)"\s*\)')


def _profileMailRoots(profile:Path)->typing.Iterable[Path]:
    """
    Directories in a Thunderbird-style profile that may hold mail,
    including custom locations configured in prefs.js.
    """
    yield profile/'Mail'
    yield profile/'ImapMail'
    try:
        text=(profile/'prefs.js').read_text(encoding='utf-8',errors='replace')
    except OSError:
        return
    for m in _PREF_RE.finditer(text):
        try:
            value=json.loads('"'+m.group(3)+'"')
        except ValueError:
            continue
        if m.group(2): # relative to the profile directory
            if value.startswith('[ProfD]'):
                yield profile/value[len('[ProfD]'):]
        else:
            yield Path(value)


def _profilesUnder(root:Path)->typing.Iterable[Path]:
    """
    Candidate profile directories for a Thunderbird-style data root.
    """
    yield root
    ini=root/'profiles.ini'
    if ini.is_file():
        parser=configparser.ConfigParser(interpolation=None)
        try:
            parser.read(ini,encoding='utf-8')
        except (configparser.Error,OSError):
            pass
        for section in parser.sections():
            raw=parser.get(section,'Path',fallback=None)
            if raw:
                p=Path(raw)
                if parser.get(section,'IsRelative',fallback='1')=='1':
                    p=root/p
                yield p
    for container in (root,root/'Profiles'):
        try:
            if container.is_dir():
                yield from (c for c in sorted(container.iterdir())
                    if c.is_dir())
        except OSError:
            pass


def findLocalMailSources(
    feedStore:FeedStore,
    ignore:typing.Optional[
        typing.Iterable[typing.Union[EmailSource,Path,str]]]=None
    )->typing.Iterable[EmailSource]:
    """
    autodetect all Mbox/Maildir mailboxes in use, one source per mailbox
    (Thunderbird, Betterbird, and generic Unix mail locations).
    """
    ignoreDirs:typing.Set[Path]=set()
    if ignore is not None:
        for source in ignore:
            if isinstance(source,LocalEmailSource):
                ignoreDirs.add(Path(source.path).resolve())
            elif isinstance(source,Path):
                ignoreDirs.add(source.resolve())
            elif isinstance(source,str):
                ignoreDirs.add(Path(source).resolve())
    found:typing.List[LocalEmailSource]=[]
    def check(mb:Path)->None:
        """
        Add a source for the mailbox unless already seen.
        """
        try:
            resolved=mb.resolve()
        except OSError:
            return
        if resolved not in ignoreDirs:
            ignoreDirs.add(resolved)
            found.append(LocalEmailSource(
                {'path':str(resolved)}, # type: ignore
                feedStore))
    home=Path.home()
    env=os.environ
    appRoots:typing.List[Path]=[] # Thunderbird-style application data dirs
    genericRoots:typing.List[Path]=[]
    if os.name=='nt':
        for var in ('APPDATA','LOCALAPPDATA'):
            base=env.get(var)
            if base:
                for app in ('Thunderbird','Betterbird'):
                    appRoots.append(Path(base)/app)
        appRoots.append(home/'AppData'/'Roaming'/'Thunderbird')
        appRoots.append(home/'AppData'/'Roaming'/'Betterbird')
        local=env.get('LOCALAPPDATA')
        if local:
            # Microsoft Store packaged versions
            try:
                for pkg in (Path(local)/'Packages').glob('*[Tt]hunderbird*'):
                    appRoots.append(pkg/'LocalCache'/'Roaming'/'Thunderbird')
                for pkg in (Path(local)/'Packages').glob('*[Bb]etterbird*'):
                    appRoots.append(pkg/'LocalCache'/'Roaming'/'Betterbird')
            except OSError:
                pass
    else:
        for name in ('.thunderbird','.betterbird'):
            appRoots.append(home/name)
        appRoots.append(home/'.config'/'thunderbird')
        appRoots.append(home/'.config'/'betterbird')
        appRoots.append(home/'snap'/'thunderbird'/'common'/'.thunderbird')
        # macOS
        appRoots.append(home/'Library'/'Thunderbird')
        appRoots.append(home/'Library'/'Application Support'/'Thunderbird')
        appRoots.append(home/'Library'/'Application Support'/'Betterbird')
        flatpakDir=home/'.var'/'app'
        for appId in ('org.mozilla.Thunderbird','eu.betterbird.Betterbird'):
            appRoots.append(flatpakDir/appId/'.thunderbird')
            appRoots.append(flatpakDir/appId/'.betterbird')
            appRoots.append(flatpakDir/appId/'config'/'thunderbird')
        genericRoots+=[home/'Maildir',home/'mbox',home/'Mail',home/'mail']
        user=env.get('USER') or env.get('LOGNAME')
        if user:
            genericRoots+=[Path('/var/mail')/user,Path('/var/spool/mail')/user]
        for var in ('MAIL','MAILDIR'):
            if env.get(var):
                genericRoots.append(Path(env[var]))
        for entry in env.get('MAILPATH','').split(':'):
            if entry:
                genericRoots.append(Path(entry.split('?',1)[0]))
    seenProfiles:typing.Set[Path]=set()
    for appRoot in appRoots:
        for profile in _profilesUnder(appRoot):
            try:
                profile=profile.resolve()
                if profile in seenProfiles or not profile.is_dir():
                    continue
            except OSError:
                continue
            seenProfiles.add(profile)
            for mailRoot in _profileMailRoots(profile):
                for mb in scanForMailboxes(mailRoot):
                    check(mb)
    for root in genericRoots:
        for mb in scanForMailboxes(root):
            check(mb)
    return found
