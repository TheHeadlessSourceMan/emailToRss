#!/usr/bin/env python3
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
import typing
import threading
import time
from pathlib import Path
from rssServer import rebuildFeed,startRssServer
from emailSources import EmailSource,getEmailSources
from feedStore import FeedStore
from feedState import FeedState
from settings import Settings


def startEmailToRssServer(settingsFile:typing.Union[None,str,Path]=None)->None:
    """
    Load settings, start polling, and serve the feed.

    This consists of two threads:
    1. The email polling and feed rebuilding thread.
    2. The RSS server thread.
    """
    store=FeedStore()
    state=FeedState()
    settings=Settings(settingsFile)
    rebuildFeed(settings,store,state)
    def emailToRssConverterThread(
        settings:Settings,
        store:FeedStore,
        state:FeedState
        )->None:
        """
        Poll all sources forever, rebuilding
        the feed whenever anything changes.
        """
        sources:typing.List[EmailSource]=list(getEmailSources(settings,store))
        print('Watching email sources:')
        if not sources:
            raise Exception("No email sources found.  Please configure.")
        for source in sources:
            print(f'\t{source.name}')
        while True:
            changed=False
            for source in sources:
                try:
                    changed=source.poll() or changed
                except Exception as e: # pylint: disable=broad-exception-caught
                    print('source error',e)
            if changed:
                rebuildFeed(settings,store,state)
            time.sleep(settings.get('pollSeconds',60))
    threading.Thread(
        target=emailToRssConverterThread,
        args=(settings,store,state),
        daemon=True).start()
    startRssServer(settings,state,serveForever=True)


def main(args:typing.Iterable[str])->int:
    """
    Main program entrypoint.

    Expects argv WITHOUT the program name.
    """
    printhelp=False
    settingsFile:typing.Optional[str]=None
    for arg in args:
        if not arg:
            continue
        if arg[0]=='-':
            kw=arg.split('=',1)
            if kw[0] in ('-h','--help'):
                printhelp=True
            elif kw[0] in ('-c','--config'):
                if len(kw)>1:
                    settingsFile=kw[1]
            else:
                print('Unknown option:',kw[0])
                printhelp=True
        else:
            print('Unknown argument:',arg)
            printhelp=True
    if printhelp:
        print("Usage: emailToRssServer.py [options]")
        print("Options:")
        print("  -h, --help       Show this help message and exit")
        print("  -c, --config=FILE  Specify the path to the config.yaml file")
        return 1
    startEmailToRssServer(settingsFile)
    return 0


if __name__=='__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
