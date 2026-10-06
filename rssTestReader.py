#!/usr/bin/env python3
"""
A quick and dirty RSS reader for testing.

All is does is read the feed and whenever something new
comes in, barf it out to stdout.
"""
import typing
from pathlib import Path
import time
import urllib.request
import xml.etree.ElementTree as ET


HERE=Path('__file__').absolute().parent
SEEN_FILENAME=HERE/'data'/'seen.dat'


NewRssItemCB=typing.Callable[
    [str,str,str],None] # cb(title,contents,url)
def simpleRssReader(
    url:str,
    onNewItem:typing.Optional[NewRssItemCB]=None,
    pollIntervalSeconds:float=60
    )->None:
    """
    Read an RSS feed forever.

    If there is a callback, send new feed entries to that.
    Otherwise, dump to stdout.
    """
    seen:typing.Set[str]=set()
    if SEEN_FILENAME.exists():
        data=SEEN_FILENAME.read_text(encoding='utf-8',errors='ignore')
        for line in data.splitlines():
            seen.add(line)
    while True:
        try:
            with urllib.request.urlopen(url) as response:
                xml_data = response.read()
            root = ET.fromstring(xml_data)
            sawMore=False
            for item in root.findall(".//item"):
                guid=item.findtext("guid")\
                    or item.findtext("link")\
                    or item.findtext("title")
                if guid is not None and guid not in seen:
                    seen.add(guid)
                    sawMore=True
                    articleTitle=item.findtext("title","(no title)")
                    articleDescription=item.findtext("description","")
                    articleUrl=item.findtext("link","")
                    if onNewItem is not None:
                        onNewItem(articleTitle,articleDescription,articleUrl)
                    else:
                        print()
                        print(articleTitle)
                        print('_'*len(articleTitle))
                        if articleUrl:
                            print(articleUrl)
                        print(articleDescription)
            if sawMore:
                SEEN_FILENAME.write_text('\n'.join(seen))
            time.sleep(pollIntervalSeconds)
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(pollIntervalSeconds)


def main(args:typing.Iterable[str])->int:
    """
    Main program entrypoint.

    Expects argv WITHOUT the program name.
    """
    printhelp=False
    pollingInterval=5
    rssUrl:typing.Optional[str]=None
    for arg in args:
        if arg[0]=='-':
            kw=arg.split('=',1)
            if kw[0] in ('-h','--help'):
                printhelp=True
            elif kw[0] in ('-i','--interval'):
                pollingInterval=float(kw[1])
            else:
                print('Unknown option:',kw[0])
                printhelp=True
        else:
            rssUrl=arg
    if rssUrl is None:
        print("ERR: No rss url given")
        printhelp=True
    if printhelp:
        print("Usage: rssTestReader.py [options] rss_url")
        print("Options:")
        print("  -h, --help       Show this help message and exit")
        print("  -i, --interval=sec  Set the polling interval in seconds (default=5)") # noqa: E501
        return 1
    rssUrl=typing.cast(str,rssUrl)
    simpleRssReader(rssUrl,None,pollingInterval)
    return 0


if __name__=='__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
