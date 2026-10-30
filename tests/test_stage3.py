"""Independent CLI checks for the Stage 3 interface."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "compiler.py"

class Stage3CLITests(unittest.TestCase):
    def test_optimize_flag_between_positionals(self):
        source = ROOT / "tests" / "e2e" / "loops_nested.em"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.ll"
            result = subprocess.run([sys.executable, str(COMPILER), str(source),
                                     "--optimize", str(output)],
                                    capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())

    def test_unrecognized_option_has_single_formatted_diagnostic(self):
        result = subprocess.run([sys.executable, str(COMPILER), "--unknown"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("compilation error: line 1:1:"))
        self.assertEqual(result.stderr.count("\n"), 1)

    def test_optimized_ast_removes_unused_chain(self):
        source = ROOT / "tests" / "optimizer" / "variables_chain.em"
        result = subprocess.run([sys.executable, str(COMPILER), "--ast", str(source),
                                 "--optimize"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("VarDecl", result.stdout)
        self.assertIn("Print", result.stdout)

if __name__ == "__main__":
    unittest.main()
