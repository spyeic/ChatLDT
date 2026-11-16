"""Package the same Open WebUI frontend; no model/execution resource downloads."""

import shutil
import subprocess
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        super().initialize(version, build_data)
        npm = shutil.which('npm')
        if not npm:
            raise RuntimeError('Node 22/npm is required to build the Open WebUI frontend')
        subprocess.run([npm, 'ci'], check=True)
        subprocess.run([npm, 'run', 'build'], check=True)
