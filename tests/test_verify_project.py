from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import verify_project


class VerifyProjectTests(unittest.TestCase):
    def test_success_runs_all_steps_with_repository_root_and_current_interpreter(self):
        calls: list[tuple[tuple[str, ...], dict]] = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as td:
            output_root = Path(td) / "out" / "verification"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = verify_project.run_verification(
                    repo_root=Path(td),
                    output_root=output_root,
                    runner=fake_run,
                    run_name="success",
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(calls), 4)
            self.assertTrue(all(kwargs["cwd"] == Path(td).resolve() for _, kwargs in calls))
            self.assertTrue(all(command[0] == sys.executable for command, _ in calls[:3]))
            self.assertEqual(calls[3][0], ("git", "diff", "--check"))

            run_dir = output_root / "success"
            self.assertTrue((run_dir / "pytest.log").is_file())
            self.assertTrue((run_dir / "housing-offline-eval.log").is_file())
            self.assertTrue((run_dir / "economic-offline-eval.log").is_file())
            self.assertTrue((run_dir / "diff-check.log").is_file())
            self.assertIn("--output", calls[1][0])
            self.assertIn(str(run_dir / "housing-question-eval.json"), calls[1][0])
            self.assertIn(str(run_dir / "economic-question-eval.json"), calls[2][0])
            self.assertIn("Doğrulama başarılı: 4/4 adım.", buffer.getvalue())

    def test_first_failure_stops_later_steps_and_shows_limited_log_tail(self):
        calls: list[tuple[str, ...]] = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if len(calls) == 2:
                kwargs["stdout"].write("ayrıntılı hata\nson satır\n")
                return SimpleNamespace(returncode=3)
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as td:
            output_root = Path(td) / "out" / "verification"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = verify_project.run_verification(
                    repo_root=Path(td),
                    output_root=output_root,
                    runner=fake_run,
                    run_name="failure",
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][1:4], ("-m", "pytest", "-q"))
            self.assertIn("scripts.evaluate_housing_questions", calls[1])
            self.assertIn("çıkış kodu 3", buffer.getvalue())
            self.assertIn("ayrıntılı hata\nson satır", buffer.getvalue())
            self.assertFalse((output_root / "failure" / "diff-check.log").exists())

    def test_command_that_cannot_start_fails_clearly(self):
        def fake_run(command, **kwargs):
            raise FileNotFoundError("eksik program")

        with tempfile.TemporaryDirectory() as td:
            output_root = Path(td) / "out" / "verification"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = verify_project.run_verification(
                    repo_root=Path(td),
                    output_root=output_root,
                    runner=fake_run,
                    run_name="launch-error",
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("komut başlatılamadı", buffer.getvalue())
            self.assertIn("eksik program", buffer.getvalue())
            log = output_root / "launch-error" / "pytest.log"
            self.assertIn("Adım başlatılamadı", log.read_text(encoding="utf-8"))

    def test_main_uses_repository_root_when_started_from_another_directory(self):
        calls: list[tuple[tuple[str, ...], dict]] = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as td:
            previous = Path.cwd()
            buffer = io.StringIO()
            try:
                os.chdir(td)
                with patch.object(
                    verify_project, "VERIFICATION_ROOT", Path(td) / "out" / "verification"
                ), patch.object(verify_project.subprocess, "run", side_effect=fake_run):
                    with redirect_stdout(buffer):
                        exit_code = verify_project.main([])
            finally:
                os.chdir(previous)

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(calls), 4)
            self.assertTrue(all(kwargs["cwd"] == verify_project.ROOT for _, kwargs in calls))
            self.assertEqual(calls[0][0][0], sys.executable)


if __name__ == "__main__":
    unittest.main()
