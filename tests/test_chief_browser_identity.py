"""Chief tab title and favicon (REQ-20260831-013-wfow)."""

import os
import struct
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")
SERVER = os.path.join(ROOT, "bin", "s9")
FAVICON = os.path.join(ROOT, "web", "favicon.png")


class ChiefBrowserIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.web = handle.read()
        with open(SERVER, encoding="utf-8") as handle:
            cls.server = handle.read()

    def test_static_and_dynamic_titles_are_chief(self):
        self.assertIn("<title>Chief</title>", self.web)
        start = self.web.index("function updateTitle")
        end = self.web.index("function stopChat", start)
        update = self.web[start:end]
        self.assertIn('document.title = "Chief"', update)
        self.assertNotIn('"section9"', update)

    def test_favicon_link_is_proxy_relative(self):
        self.assertIn('<link rel="icon" type="image/png" href="favicon.png">', self.web)
        self.assertNotIn('href="/favicon.png"', self.web)

    def test_favicon_is_a_real_192_png(self):
        with open(FAVICON, "rb") as handle:
            data = handle.read(24)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (192, 192))

    def test_server_has_fixed_favicon_route(self):
        self.assertIn('elif parsed.path == "/favicon.png":', self.server)
        self.assertIn('self._send(200, "image/png", f.read())', self.server)


if __name__ == "__main__":
    unittest.main(verbosity=2)
