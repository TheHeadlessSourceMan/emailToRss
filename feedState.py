"""
Thread-safe holder of the current rendered feed snapshot.
"""
import threading


class FeedState:
    """
    Thread-safe holder of the current rendered feed snapshot.
    """

    def __init__(self)->None:
        self._lock=threading.Lock()
        self._feed=''

    @property
    def feed(self)->str:
        """
        The current rss xml document.
        """
        with self._lock:
            return self._feed

    @feed.setter
    def feed(self,snapshot:str)->None:
        with self._lock:
            self._feed=snapshot
