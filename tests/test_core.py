import tempfile
import unittest
from pathlib import Path
from core import (
    allowed_host, normalize_url, is_file_href, parse_download_links, has_next_page,
    safe_name, hash_file, completed_file_valid, available_path, atomic_json,
)


class TestURLs(unittest.TestCase):
    def test_hosts(self):
        for host in ("ux", "uu", "u1", "u8", "u100"):
            self.assertTrue(allowed_host(host + ".getuploader.com"))
            base, slug = normalize_url(f"https://{host}.getuploader.com/demo/")
            self.assertEqual((base, slug), (f"https://{host}.getuploader.com/demo/", "demo"))
        self.assertFalse(allowed_host("uu.getuploader.com.evil.org"))

    def test_reject_non_site_urls(self):
        for bad in (
            "http://uu.getuploader.com/a/", "https://evil.com/a/", "https://uu.getuploader.com/",
            "https://uu.getuploader.com@evil.com/a/", "https://uu.getuploader.com:8080/a/",
            "https://uu.getuploader.com/a/?x=1", "https://u1.getuploader.com.evil.org/a/",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_url(bad)

    def test_file_links(self):
        base = "https://u1.getuploader.com/demo/"
        self.assertEqual(is_file_href("/demo/download/32", "demo", base), base + "download/32")
        self.assertIsNone(is_file_href("https://evil.com/demo/download/32", "demo", base))
        self.assertIsNone(is_file_href("https://u1.getuploader.com/demo/download/32?redirect=https://evil.com", "demo", base))
        links = [
            {"href": "/demo/download/2", "text": "a.zip"},
            {"href": "/demo/download/2", "text": "a.zip"},
            {"href": "/other/download/2", "text": "b.zip"},
        ]
        self.assertEqual(len(parse_download_links(links, "demo", base)), 1)

    def test_next_page(self):
        base = "https://uu.getuploader.com/demo/index/date/desc/1"
        self.assertTrue(has_next_page([{"href": "/demo/index/date/desc/2"}], "demo", base, 2))
        self.assertFalse(has_next_page([{"href": "/demo/index/date/desc/20"}], "demo", base, 2))
        self.assertFalse(has_next_page([{"href": "https://evil.com/demo/index/date/desc/2"}], "demo", base, 2))


class TestStorage(unittest.TestCase):
    def test_safe_name(self):
        self.assertEqual(safe_name("../../evil?.zip", "3"), "evil_.zip")
        self.assertTrue(safe_name("CON", "5").startswith("file_5"))
        self.assertTrue(safe_name("a" * 999, "4").__len__() <= 170)

    def test_hash_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            data = target / "1_x.zip"
            data.write_bytes(b"hello")
            record = {"status": "done", "filename": data.name, "bytes": 5, "sha256": hash_file(data)}
            self.assertTrue(completed_file_valid(target, record))
            data.write_bytes(b"world")
            self.assertFalse(completed_file_valid(target, record))
            record["filename"] = "../elsewhere"
            self.assertFalse(completed_file_valid(target, record))

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            (target / "1_file.zip").write_bytes(b"user content")
            self.assertEqual(available_path(target, "1_file.zip").name, "1_file (2).zip")
            self.assertEqual((target / "1_file.zip").read_bytes(), b"user content")

    def test_atomic_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "manifest.json"
            atomic_json(target, {"uploader": "demo", "files": {}})
            self.assertIn("demo", target.read_text(encoding="utf-8"))
            self.assertEqual(list(Path(d).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
