"""Exercise the installed artifact without falling back to the checkout."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest


def test_wheel_includes_runtime_assets(tmp_path):
    if any(importlib.util.find_spec(name) is None for name in ("pip", "setuptools", "wheel")):
        pytest.skip("building a wheel requires pip, setuptools, and wheel")
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "setup.py", "MANIFEST.in"):
        shutil.copy(root / name, source / name)
    for name in ("src", "packs", "guard"):
        shutil.copytree(root / name, source / name, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.egg-info", "state.json", "events.jsonl", "archive", "PAUSED"))
    env = {**os.environ, "PYTHONPATH": ""}
    subprocess.run([sys.executable, "-c", "import setuptools.build_meta as b; b.build_sdist('dist')"],
                   cwd=source, check=True, capture_output=True, text=True, env=env, timeout=120)
    sdist = next((source / "dist").glob("fleetwork-*.tar.gz"))
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-index",
                    "--no-build-isolation", "--wheel-dir", str(tmp_path), str(sdist)],
                   check=True, capture_output=True, text=True, env=env, timeout=120)
    wheel = next(tmp_path.glob("fleetwork-*.whl"))
    installed = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(installed)
    env["PYTHONPATH"] = str(installed)
    target = tmp_path / "ledger"
    init_args = ["init", "--dir", str(target), "--packs", "core,git"]
    for var in ("owner", "provider", "runtime", "model"):
        init_args.extend(["--var", f"{var}=test"])
    for args in (init_args, ["guard", "--", "--help"]):
        result = subprocess.run([sys.executable, "-m", "fleetwork.runtime.cli", *args],
                                cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    assert (target / "seed.yaml").is_file()
    assert (target / "rules" / "git.md").is_file()
