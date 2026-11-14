import json
import subprocess
import unittest
from unittest.mock import patch

from mimictype.core.layout_detector import LayoutDetector


class TestLayoutDetector(unittest.TestCase):
    def test_kde_json_with_non_empty_variant(self):
        layouts_json = json.dumps(
            {
                "type": "a(sss)",
                "data": [
                    [
                        ["us", "altgr-intl", "English (US, intl.)"],
                        ["ru", "winkeys", "Russian (Winkeys)"],
                    ]
                ],
            }
        )
        active_json = json.dumps({"type": "u", "data": [1]})

        responses = [
            subprocess.CompletedProcess([], 0, stdout=layouts_json),
            subprocess.CompletedProcess([], 0, stdout=active_json),
            subprocess.CompletedProcess([], 0, stdout=""),
        ]

        with (
            patch("mimictype.core.layout_detector.shutil.which", side_effect=lambda cmd: "/usr/bin/busctl" if cmd == "busctl" else None),
            patch("mimictype.core.layout_detector.subprocess.run", side_effect=responses) as mock_run,
        ):
            detector = LayoutDetector()
            self.assertEqual(detector._kde_layouts_map, {"us": 0, "ru": 1})
            self.assertEqual(detector.get_active_layout(), "ru")
            self.assertTrue(detector.switch_layout_direct("us"))
            self.assertIn("0", mock_run.call_args_list[-1][0][0])

    def test_kde_gvariant_fallback_with_winkeys(self):
        raw = 'a(sss) 2 "us" "" "English (US)" "ru" "winkeys" "Russian"'
        parsed = LayoutDetector._parse_kde_layouts(raw)
        self.assertEqual(parsed, {"us": 0, "ru": 1})
        self.assertEqual(LayoutDetector._parse_kde_active_index("u 1\n"), 1)

    def test_x11_multilayout_uses_active_group_not_first(self):
        setxkbmap_out = "rules:      evdev\nmodel:      pc105\nlayout:     us,ru\nvariant:    ,winkeys\n"

        def fake_which(cmd):
            if cmd == "setxkbmap":
                return "/usr/bin/setxkbmap"
            return None

        with (
            patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True),
            patch("mimictype.core.layout_detector.shutil.which", side_effect=fake_which),
            patch(
                "mimictype.core.layout_detector.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout=setxkbmap_out),
            ),
            patch.object(LayoutDetector, "_get_x11_active_group", return_value=1),
        ):
            detector = LayoutDetector()
            self.assertEqual(detector.get_active_layout(), "ru")

    def test_x11_multilayout_unknown_group_does_not_default_to_first(self):
        setxkbmap_out = "layout:     us,ru\n"

        with (
            patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True),
            patch(
                "mimictype.core.layout_detector.shutil.which",
                side_effect=lambda cmd: "/usr/bin/setxkbmap" if cmd == "setxkbmap" else None,
            ),
            patch(
                "mimictype.core.layout_detector.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout=setxkbmap_out),
            ),
            patch.object(LayoutDetector, "_get_x11_active_group", return_value=None),
        ):
            detector = LayoutDetector()
            self.assertIsNone(detector.get_active_layout())


if __name__ == "__main__":
    unittest.main()
