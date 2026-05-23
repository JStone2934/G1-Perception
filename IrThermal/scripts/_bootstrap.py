"""将 IrThermal/packages/irthermal 加入 sys.path（未 pip install 时脚本仍可运行）。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_IR_SRC = _ROOT / "packages" / "irthermal" / "src"
if _IR_SRC.is_dir():
    s = str(_IR_SRC)
    if s not in sys.path:
        sys.path.insert(0, s)
