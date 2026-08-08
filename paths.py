# -*- coding: utf-8 -*-
import sys
from pathlib import Path


def game_root():
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        if sys.platform == "darwin" and ".app" in str(executable):
            for parent in executable.parents:
                if parent.suffix == ".app":
                    return parent.parent
        return executable.parent
    return Path(__file__).resolve().parent.parent


def image_path(name):
    return str(game_root() / "images" / name)


def font_path(name="PressStart2P-Regular.ttf"):
    return str(game_root() / "fonts" / name)
