"""stack config parsing and content-addressed tags for Compose-built images."""
import unittest
from unittest import mock

from dojo import stack
from dojo.start import _content_image_tags

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


BUILT = {"services": {
    "sensei-a": {"build": {"context": "../modules/sensei", "args": {}},
                 "image": "gitopsdojo/sensei:git-fundamentals"},
    "sensei-b": {"build": {"context": "../modules/sensei", "args": {}},
                 "image": "gitopsdojo/sensei:tofu-basics"},
    "runner-pool": {"build": {"context": "../modules/runner-pool/pool",
                                "args": {"JOB_TOOLS": "tofu"}},
                    "image": "gitopsdojo/runner-pool:cloud-policy-as-code"},
    "runner-alias": {"image": "gitopsdojo/runner-pool:cloud-policy-as-code"},
    "external": {"image": "docker.io/library/alpine:3"},
}}


class BuildImages(unittest.TestCase):
  def test_build_specs_only_include_services_with_build_blocks(self):
    self.assertEqual(set(stack.parse_build_specs(BUILT)), {"sensei-a", "sensei-b", "runner-pool"})

  def test_service_images_include_aliases_and_compose_defaults(self):
    images = stack.parse_service_images(BUILT)
    self.assertEqual(images["runner-alias"], "gitopsdojo/runner-pool:cloud-policy-as-code")
    self.assertEqual(images["sensei-a"], "gitopsdojo/sensei:git-fundamentals")

  def test_rendered_override_is_deterministic(self):
    images = {"sensei": "gitopsdojo/sensei:local", "runner-pool": "gitopsdojo/runner-pool:cloud-policy-as-code"}
    hashes = {"sensei": "abcd", "runner-pool": "1234"}
    self.assertEqual(stack.render_image_override(images, hashes),
                     stack.render_image_override(dict(reversed(list(images.items()))), hashes))

  def test_identical_inputs_share_a_tag_and_aliases_follow_it(self):
    from dojo.runtime import Runtime
    with mock.patch("dojo.start.config_document", return_value=BUILT):
      build_tags, hashes, overrides = _content_image_tags(Runtime(), [], {})
    self.assertEqual(hashes["sensei-a"], hashes["sensei-b"])
    self.assertEqual(overrides["sensei-a"], "gitopsdojo/sensei:git-fundamentals")
    self.assertNotEqual(hashes["sensei-a"], hashes["runner-pool"])


if __name__ == "__main__":
    unittest.main()
