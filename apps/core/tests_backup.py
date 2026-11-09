import subprocess
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase


class BackupTests(SimpleTestCase):
    @patch(
        "apps.core.management.commands.backup_database.shutil.which",
        return_value="pg_dump",
    )
    @patch("apps.core.management.commands.backup_database.subprocess.run")
    def test_existing_backup_is_not_replaced(self, run, which):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "backup.dump"
            path.write_bytes(b"existing")
            with self.assertRaises(CommandError):
                call_command("backup_database", str(path), stdout=StringIO())
            self.assertEqual(path.read_bytes(), b"existing")
            run.assert_not_called()

    @patch(
        "apps.core.management.commands.backup_database.shutil.which",
        return_value="pg_dump",
    )
    @patch(
        "apps.core.management.commands.backup_database.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "pg_dump"),
    )
    def test_failed_backup_does_not_leave_partial_file(self, run, which):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "failed.dump"
            with self.assertRaises(CommandError):
                call_command("backup_database", str(path), stdout=StringIO())
            self.assertFalse(path.exists())
