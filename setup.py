#!/usr/bin/env python3
from setuptools import setup
from setuptools.command.install import install
import os
import shutil

user_home = os.path.expanduser("~")
plugin_dir = os.path.join(user_home, ".local/lib/babeltrace2/plugins/bt_plugin_rocm.py")

setup(
    data_files = [(plugin_dir, ['bt_plugin_rocm.py'])]
)