"""
SQLite-backed storage of feed items, unique by guid.

While you're there pick up some oats for the horses. ;)
"""
import sqlite3
import typing
from datetime import datetime, timezone


DEFAULT_DB='rss_bridge.db'
ItemRow=typing.Tuple[str,str,str,str]


class FeedStore:
    """
    SQLite-backed storage of feed items, unique by guid.

    While you're there pick up some oats for the horses. ;)
    """

    def __init__(self,db:str=DEFAULT_DB):
        """
        :db: path to the sqlite database file
        """
        self.db=db
        self.init()

    def conn(self)->sqlite3.Connection:
        """
        Open a new database connection.
        """
        return sqlite3.connect(self.db)

    def init(self)->None:
        """
        Create the items table if it does not exist.
        """
        c=self.conn()
        c.execute('create table if not exists items('
            'guid text primary key,title text,body text,pubdate text)')
        c.commit()
        c.close()

    def add(self,guid:str,title:str,body:str)->bool:
        """
        Add an item.

        :return: True if added, False if the guid was already present
        """
        pubDate=datetime.now(timezone.utc).strftime(
            '%a, %d %b %Y %H:%M:%S GMT')
        c=self.conn()
        try:
            c.execute('insert into items values(?,?,?,?)',
                (guid,title,body,pubDate))
            c.commit()
            ok=True
        except sqlite3.IntegrityError:
            ok=False
        c.close()
        return ok

    def items(self)->typing.List[ItemRow]:
        """
        Get all items as (guid,title,body,pubdate), newest first.
        """
        c=self.conn()
        rows=c.execute('select guid,title,body,pubdate '
            'from items order by rowid desc').fetchall()
        c.close()
        return rows
