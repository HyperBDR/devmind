from tempfile import NamedTemporaryFile

from django.test import SimpleTestCase

from core.file_hash import hash_file


class FileHashTests(SimpleTestCase):
    def test_hash_file_reads_binary_content(self):
        with NamedTemporaryFile() as temporary:
            temporary.write(b"invoice")
            temporary.flush()

            self.assertEqual(
                hash_file(temporary.name),
                (
                    "52d6e3de4fa0dcc29946695f93940c3e7f26f30e1e39f4b1a49ad"
                    "98839112786"
                ),
            )
