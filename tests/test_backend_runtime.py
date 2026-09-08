"""Exercise startup, all workspaces, journals and profile changes with Tk blocked."""
import subprocess
import sys
import unittest
from pathlib import Path

class BackendRuntimeTests(unittest.TestCase):
    def test_application_without_tk(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / "tests/backend_runtime_smoke.py")],
                                cwd=root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CLOSED WITHOUT TK", result.stdout)
