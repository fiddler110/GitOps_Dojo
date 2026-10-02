"""stack.parse_mem_limits: what `./run.sh capacity WORKSHOP` counts."""
import unittest

from dojo import stack

CONFIG = """networks:
  web_lab:
services:
  achievements:
    image: gitopsdojo/allocator:local
    mem_limit: 128m
  bootstrap:
    restart: 'no'
  cloud-host:
    mem_limit: 3g
  sensei:
    restart: unless-stopped
  web-terminal:
    mem_limit: 3G
volumes:
  data:
    name: x
"""


class MemLimits(unittest.TestCase):
    def test_parse(self):
        limits, oneshot = stack.parse_mem_limits(CONFIG)
        self.assertEqual(limits, {"achievements": 128, "bootstrap": None, "cloud-host": 3072,
                                  "sensei": None, "web-terminal": 3072})
        self.assertEqual(oneshot, ["bootstrap"])

    def test_sizes(self):
        self.assertEqual([stack._mb(v) for v in ("512m", "2g", "2048k", "1073741824", "1.5g", "big")],
                         [512, 2048, 2, 1024, 1536, None])


if __name__ == "__main__":
    unittest.main()
