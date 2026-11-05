"""Source checks only: no package inspection, elevation or real installation."""

import importlib.util
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("installer_skill", Path(__file__).with_name("install-vst3.py"))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerChecks(unittest.TestCase):
    def test_vst3_token_and_parent_selection(self):
        nodes = [{"choiceIdentifier": "vendor", "childItems": [
            {"choiceIdentifier": "vendor.VST3", "pathsOfActivePackagesInChoice": ["vst3.pkg"]},
            {"choiceIdentifier": "vendor.AU", "pathsOfActivePackagesInChoice": ["au.pkg"]},
            {"choiceIdentifier": "vendor.NotVST3", "pathsOfActivePackagesInChoice": ["other.pkg"]},
        ]}]
        selected = {item["choiceIdentifier"] for item in installer.choices(nodes) if item["attributeSetting"]}
        self.assertEqual(selected, {"vendor", "vendor.VST3"})

    def test_preview_and_failed_preflight_never_install(self):
        tree = [{"choiceIdentifier": "vendor.VST3", "pathsOfActivePackagesInChoice": ["vst3.pkg"]},
                {"choiceIdentifier": "vendor.AU", "pathsOfActivePackagesInChoice": ["au.pkg"]}]
        evaluated = [{"choiceIdentifier": "vendor.VST3", "choiceAttribute": "selected", "attributeSetting": 1}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.pkg").touch()
            (root / "b.pkg").touch()

            def output(*args):
                if "-showChoicesXML" in args:
                    return plistlib.dumps(tree)
                return plistlib.dumps(evaluated)

            with patch.object(installer, "__file__", str(root / "install-vst3.py")), \
                 patch.object(installer, "output", side_effect=output), \
                 patch.object(installer.subprocess, "run") as run:
                with patch.object(sys, "argv", ["install-vst3.py"]):
                    installer.main()
                run.assert_not_called()
                evaluated.append({"choiceIdentifier": "vendor.AU", "choiceAttribute": "selected", "attributeSetting": 1})
                with patch.object(sys, "argv", ["install-vst3.py", "--install"]):
                    with self.assertRaisesRegex(RuntimeError, "did not honor"):
                        installer.main()
                run.assert_not_called()

    def test_no_vst3_fails_before_elevation(self):
        tree = [{"choiceIdentifier": "vendor.AU", "pathsOfActivePackagesInChoice": ["au.pkg"]}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.pkg").touch()
            with patch.object(installer, "__file__", str(root / "install-vst3.py")), \
                 patch.object(installer, "output", return_value=plistlib.dumps(tree)), \
                 patch.object(installer.subprocess, "run") as run, \
                 patch.object(sys, "argv", ["install-vst3.py", "--install"]):
                with self.assertRaisesRegex(RuntimeError, "no identifiable VST3"):
                    installer.main()
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
