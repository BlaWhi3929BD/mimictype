from importlib import resources
from pathlib import Path
import unittest
from unittest.mock import patch

from mimictype import config as config_mod
from mimictype.config import MimicConfig


class TestConfigPackaging(unittest.TestCase):
    def test_no_top_level_config_namespace_collision(self):
        repo_root = Path(__file__).resolve().parent.parent
        self.assertFalse((repo_root / "config").exists())

    def test_default_yaml_bundled_as_package_data(self):
        res = resources.files("mimictype.data").joinpath("default.yaml")
        self.assertTrue(res.is_file())

    def test_load_uses_package_resource(self):
        fake_file = "/tmp/nonexistent_site/mimictype/config.py"
        with patch.object(config_mod, "__file__", fake_file):
            with patch("mimictype.config.yaml.safe_load", wraps=config_mod.yaml.safe_load) as spy_yaml:
                cfg = MimicConfig.load()
                self.assertEqual(spy_yaml.call_count, 1)
                self.assertEqual(cfg.wpm, 65)

    def test_presets_update_and_restore_dwell_and_pauses(self):
        cfg = MimicConfig()
        cfg.apply_preset("instant")
        self.assertEqual(cfg.dwell.min_seconds, 0.015)
        self.assertEqual(cfg.pauses.sentence_boundary, (0.0, 0.0))

        cfg.apply_preset("fast")
        self.assertEqual(cfg.wpm, 100)
        self.assertGreater(cfg.dwell.min_seconds, 0.02)
        self.assertGreater(cfg.dwell.max_seconds, 0.05)

        cfg.apply_preset("careful")
        self.assertEqual(cfg.wpm, 45)
        self.assertEqual(cfg.dwell.min_seconds, 0.050)
        self.assertEqual(cfg.dwell.max_seconds, 0.165)

        cfg.apply_preset("natural")
        self.assertEqual(cfg.wpm, 65)
        self.assertEqual(cfg.dwell.min_seconds, 0.045)
        self.assertEqual(cfg.dwell.max_seconds, 0.145)
        self.assertEqual(cfg.pauses.sentence_boundary, (0.35, 0.75))


if __name__ == "__main__":
    unittest.main()
