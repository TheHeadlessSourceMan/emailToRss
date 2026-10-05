"""
Tools for spinning up an RSS server.
"""
import typing
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from xml.sax.saxutils import escape

from feedStore import FeedStore
from feedState import FeedState
from settings import Settings

DEFAULT_RSS_URL_PATH='/rss' # URL path for the RSS feed
RSS_CONTENT_TYPE='application/rss+xml; charset=utf-8'
MAX_BODY_LENGTH=8000


def rebuildFeed(settings:Settings,store:FeedStore,state:FeedState)->None:
    """
    Render all stored items to rss xml and swap it in as the active feed.
    """
    parts=['<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f'<title>{escape(settings["rss"]["title"])}</title>']
    for guid,title,body,pubDate in store.items():
        parts.append('<item>')
        parts.append(f'<guid>{escape(guid)}</guid>'
            f'<title>{escape(title)}</title>'
            f'<description>{escape(body[:MAX_BODY_LENGTH])}</description>'
            f'<pubDate>{pubDate}</pubDate>')
        parts.append('</item>')
    parts.append('</channel></rss>')
    state.feed=''.join(parts)


def createRssServerHandler(
    state:FeedState
    )->typing.Type[BaseHTTPRequestHandler]:
    """
    Create a request handler class that serves the feed held by state.
    """
    class RssHandler(BaseHTTPRequestHandler):
        """
        Serves the rss feed at RSS_PATH.
        """

        def do_GET(self)->None: # pylint: disable=invalid-name
            """
            Respond to a GET request.
            """
            if self.path.split('?',1)[0]!=DEFAULT_RSS_URL_PATH:
                self.send_error(404)
                return
            data=state.feed.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type',RSS_CONTENT_TYPE)
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return RssHandler


def startRssServer(
    settings:Settings,
    state:FeedState,
    serveForever:bool=True
    )->ThreadingHTTPServer:
    """
    Start the RSS server using the provided settings and state.

    If serveForever is True (default),
    the server will block and serve indefinitely.
    """
    ip=settings['rss'].get('ip','127.0.0.1')
    port=int(settings['rss'].get('port',8080))
    urlPath=settings['rss'].get('path',DEFAULT_RSS_URL_PATH)
    server=ThreadingHTTPServer((ip,port),createRssServerHandler(state))
    domain=f"{server.server_address[0]}:{server.server_address[1]}"
    print(f"RSS server started at:\n\thttp://{domain}{urlPath}")
    if serveForever:
        server.serve_forever()
    return server
