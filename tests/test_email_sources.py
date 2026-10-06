"""Tests for email source discovery."""
import email.message
import json
import mailbox
import tempfile
import unittest
from pathlib import Path

from emailSources import (
    LocalEmailSource,
    _profileMailRoots,
    readMboxIndexTags,
    scanForMailboxes,
)
from feedStore import FeedStore
from settings import Settings


class ProfileMailRootsTests(unittest.TestCase):
    """Verify mail roots from Thunderbird-style profile preferences."""

    def setUp(self):
        self._tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.profile=Path(self._tmp.name)/"profile"
        self.profile.mkdir()

    def test_profile_relative_path_wins_over_stale_absolute_path(self):
        stale=Path(self._tmp.name)/"old-profile"/"ImapMail"
        (self.profile/"prefs.js").write_text(
            f'user_pref("mail.server.server1.directory", "{stale}");\n'
            'user_pref("mail.server.server1.directory-rel", '
            '"[ProfD]ImapMail");\n',
            encoding="utf-8",
        )

        roots=set(_profileMailRoots(self.profile))

        self.assertIn(self.profile/"ImapMail", roots)
        self.assertNotIn(stale, roots)

    def test_absolute_path_is_used_without_profile_relative_path(self):
        custom=Path(self._tmp.name)/"custom-mail"
        (self.profile/"prefs.js").write_text(
            f'user_pref("mail.server.server1.directory", "{custom}");\n',
            encoding="utf-8",
        )

        self.assertIn(custom, set(_profileMailRoots(self.profile)))


class LocalEmailSourceTests(unittest.TestCase):
    """Verify tagged messages in local Thunderbird/Betterbird mailboxes."""

    def _source(self,path:Path,store:FeedStore)->LocalEmailSource:
        settingsPath=path.parent/"source.json"
        settingsPath.write_text(
            json.dumps({"path":str(path)}),encoding="utf-8")
        return LocalEmailSource(Settings(settingsPath),store)

    def test_scan_skips_trash_junk_and_sent_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"INBOX").write_bytes(b"From sender@example.com\n")
            for name in (".Trash", "Junk", "Sent Items"):
                folder=root/name
                (folder/"cur").mkdir(parents=True)
                (folder/"new").mkdir()

            found=set(scanForMailboxes(root))

            self.assertEqual(found,{root/"INBOX"})

    def test_poll_skips_configured_trash_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"Trash"
            msg=email.message.EmailMessage()
            msg['Message-ID']='<trashed@example.com>'
            msg['Subject']='Tagged trash message'
            msg['X-Mozilla-Keys']='RSS'
            msg.set_content('Message body')
            box=mailbox.mbox(str(path))
            box.add(msg)
            box.close()

            store=FeedStore(str(Path(tmp)/'feed.db'))
            source=self._source(path,store)

            self.assertFalse(source.poll())
            self.assertEqual(store.items(),[])

    def test_poll_reads_tag_from_thunderbird_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"INBOX"
            guid='<message@example.com>'
            msg=email.message.EmailMessage()
            msg['Message-ID']=guid
            msg['Subject']='Tagged message'
            msg.set_content('Message body')
            box=mailbox.mbox(str(path))
            box.add(msg)
            box.close()
            Path(str(path)+'.msf').write_text(
                '(5506=message@example.com)(551F=nonjunk rss)'
                '[1:m(^83^5506)(^BC^551F)]',
                encoding='utf-8',
            )

            store=FeedStore(str(Path(tmp)/'feed.db'))
            source=self._source(path,store)

            self.assertTrue(source.poll())
            self.assertEqual(store.items()[0][0],guid)

    def test_poll_removes_deleted_message_from_thunderbird_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"INBOX"
            deleted=email.message.EmailMessage()
            deleted['Message-ID']='<delete@example.com>'
            deleted['Subject']='Delete this message'
            deleted.set_content('Message body')
            retained=email.message.EmailMessage()
            retained['Message-ID']='<keep@example.com>'
            retained['Subject']='Keep this message'
            retained.set_content('Message body')
            box=mailbox.mbox(str(path))
            box.add(deleted)
            box.add(retained)
            box.close()
            indexPath=Path(str(path)+'.msf')
            indexPath.write_text(
                '(5506=delete@example.com)(5507=keep@example.com)'
                '(551F=nonjunk rss+del)(5520=nonjunk rss)'
                '[1:m(^83^5506)(^BC^551F)]'
                '[2:m(^83^5507)(^BC^5520)]',
                encoding='utf-8',
            )

            store=FeedStore(str(Path(tmp)/'feed.db'))
            source=self._source(path,store)

            self.assertTrue(source.poll())
            remaining=mailbox.mbox(str(path),create=False)
            self.assertEqual(len(remaining),1)
            self.assertEqual(remaining[0]['Message-ID'],'<keep@example.com>')
            remaining.close()
            self.assertEqual(
                readMboxIndexTags(indexPath),
                {'keep@example.com':{'NONJUNK','RSS'}},
            )


if __name__ == "__main__":
    unittest.main()