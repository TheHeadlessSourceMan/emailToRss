"""Tests for email source discovery."""
import tempfile
import unittest
from pathlib import Path

from emailSources import _profileMailRoots


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


if __name__ == "__main__":
    unittest.main()