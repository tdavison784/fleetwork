"""Include the repository's runtime assets in built distributions."""
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithAssets(build_py):
    def run(self):
        super().run()
        root = Path(__file__).parent
        destination = Path(self.build_lib) / "fleetwork" / "_assets"
        for source in (root / "packs").rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts:
                target = destination / "packs" / source.relative_to(root / "packs")
                self.mkpath(str(target.parent))
                self.copy_file(str(source), str(target))
        for name in ("fleet_guard.py", "lead_hook.sh"):
            target = destination / "guard" / name
            self.mkpath(str(target.parent))
            self.copy_file(str(root / "guard" / name), str(target))


setup(cmdclass={"build_py": BuildWithAssets})
