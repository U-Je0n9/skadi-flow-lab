"""Build the current v2 design and GitHub Pages assets from sanitized fixtures."""
import subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parent
for name in ('design.py','make_traces.py','write_document.py','build.py'):
    subprocess.run([sys.executable,str(root/'v2'/name)],check=True)
