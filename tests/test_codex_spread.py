import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "spread_codex_caveman.py"


class SpreadCodexCavemanTests(unittest.TestCase):
    def run_cmd(self, *args):
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory(prefix="caveman-codex-dry-run-") as tmp:
            repo = Path(tmp) / "alpha"
            (repo / ".git").mkdir(parents=True)

            result = self.run_cmd(str(repo))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DRY RUN", result.stdout)
            self.assertFalse((repo / ".codex").exists())

    def test_apply_creates_codex_files_for_new_repo(self):
        with tempfile.TemporaryDirectory(prefix="caveman-codex-apply-") as tmp:
            repo = Path(tmp) / "alpha"
            (repo / ".git").mkdir(parents=True)

            result = self.run_cmd("--apply", str(repo))

            self.assertEqual(result.returncode, 0, result.stderr)

            hooks = json.loads((repo / ".codex" / "hooks.json").read_text())
            session_start = hooks["hooks"]["SessionStart"]
            self.assertEqual(len(session_start), 1)
            self.assertEqual(session_start[0]["matcher"], "startup|resume")
            self.assertIn("CAVEMAN MODE ACTIVE", session_start[0]["hooks"][0]["command"])

            config_text = (repo / ".codex" / "config.toml").read_text()
            self.assertIn("[features]", config_text)
            self.assertIn("hooks = true", config_text)
            self.assertNotIn("codex_hooks", config_text)

    def test_apply_merges_existing_codex_files(self):
        with tempfile.TemporaryDirectory(prefix="caveman-codex-merge-") as tmp:
            repo = Path(tmp) / "alpha"
            codex_dir = repo / ".codex"
            (repo / ".git").mkdir(parents=True)
            codex_dir.mkdir()

            existing_hooks = {
                "hooks": {
                    "Notification": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "echo keep-me",
                                }
                            ]
                        }
                    ],
                    "SessionStart": [
                        {
                            "matcher": "startup",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "echo existing-start",
                                }
                            ],
                        }
                    ],
                }
            }
            (codex_dir / "hooks.json").write_text(json.dumps(existing_hooks, indent=2) + "\n")
            (codex_dir / "config.toml").write_text("[features]\nother_flag = true\n")

            result = self.run_cmd("--apply", str(repo))

            self.assertEqual(result.returncode, 0, result.stderr)

            hooks = json.loads((codex_dir / "hooks.json").read_text())
            self.assertEqual(len(hooks["hooks"]["Notification"]), 1)
            self.assertEqual(len(hooks["hooks"]["SessionStart"]), 2)
            self.assertEqual(
                hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"],
                "echo existing-start",
            )
            self.assertIn(
                "CAVEMAN MODE ACTIVE",
                hooks["hooks"]["SessionStart"][1]["hooks"][0]["command"],
            )

            config_text = (codex_dir / "config.toml").read_text()
            self.assertIn("other_flag = true", config_text)
            self.assertIn("hooks = true", config_text)
            self.assertNotIn("codex_hooks", config_text)

    def test_apply_migrates_old_codex_hook_flag(self):
        cases = [
            ("old true", "[features]\ncodex_hooks = true\n"),
            ("old false", "[features]\ncodex_hooks = false\n"),
            ("new false", "[features]\nhooks = false\n"),
            ("both keys", "[features]\nhooks = false\ncodex_hooks = true\n"),
        ]
        for name, config in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(prefix="caveman-codex-migrate-") as tmp:
                    repo = Path(tmp) / "alpha"
                    codex_dir = repo / ".codex"
                    (repo / ".git").mkdir(parents=True)
                    codex_dir.mkdir()
                    (codex_dir / "config.toml").write_text(config)

                    result = self.run_cmd("--apply", str(repo))

                    self.assertEqual(result.returncode, 0, result.stderr)
                    config_text = (codex_dir / "config.toml").read_text()
                    self.assertIn("hooks = true", config_text)
                    self.assertNotIn("codex_hooks", config_text)

    def test_dry_run_does_not_migrate_old_codex_hook_flag(self):
        with tempfile.TemporaryDirectory(prefix="caveman-codex-dry-run-migrate-") as tmp:
            repo = Path(tmp) / "alpha"
            codex_dir = repo / ".codex"
            (repo / ".git").mkdir(parents=True)
            codex_dir.mkdir()
            config_path = codex_dir / "config.toml"
            config_path.write_text("[features]\ncodex_hooks = true\n")

            result = self.run_cmd(str(repo))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("config=updated", result.stdout)
            self.assertEqual(config_path.read_text(), "[features]\ncodex_hooks = true\n")


if __name__ == "__main__":
    unittest.main()
