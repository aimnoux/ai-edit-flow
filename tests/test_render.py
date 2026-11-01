"""A selected composition renders without needing or overwriting a shared index.html."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import render
import review


class RenderProjectTests(unittest.TestCase):
    def test_isolated_stable_entry_and_local_assets_without_mutating_global_index(self):
        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder) / "engine"
            here.mkdir()
            (here / "index.html").write_text("unrelated preview")
            (here / "lib").mkdir()
            (here / "lib/finish.js").write_text("// local timing library")
            source = here / "demo-ch1.html"
            source.write_text('<div data-composition-id="demo-ch1">First</div><script src="lib/finish.js"></script>')
            commands = []
            def run_hf(*args, **kwargs):
                commands.append(args)
                staged = Path(args[1])
                self.assertTrue((staged / "index.html").is_file())
                self.assertEqual((staged / "lib/finish.js").read_text(), "// local timing library")
                return subprocess.CompletedProcess(args, 0, "rendered", "")
            with patch.object(render, "HERE", here), patch.object(review, "HERE", here), \
                    patch.object(render, "BUILD", here / "build"), patch.object(render, "run_hf", side_effect=run_hf):
                render.render("demo-ch1", here / "renders/final.mp4", "--fps", "10")
                source.write_text(source.read_text().replace("First", "Updated"))
                render.render("demo-ch1", here / "renders/final.mp4", "--resume")
            self.assertEqual(commands[0][1], commands[1][1])
            self.assertIn("Updated", (Path(commands[1][1]) / "index.html").read_text())
            self.assertEqual((here / "index.html").read_text(), "unrelated preview")
            self.assertNotIn("-c", commands[0])

    def test_invalid_id_fails_before_staging_or_browser(self):
        with patch.object(render, "project") as stage, patch.object(render, "run_hf") as hf:
            with self.assertRaises(ValueError): render.render("../outside", "out.mp4")
        stage.assert_not_called()
        hf.assert_not_called()


if __name__ == "__main__":
    unittest.main()
