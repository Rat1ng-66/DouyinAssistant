import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    """打包后的配置放在 exe 旁边，整个文件夹拷走即可带走数据。"""
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent / "data"
    else:
        root = (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "DouyinAssistant"
        )
    root.mkdir(parents=True, exist_ok=True)
    return root
