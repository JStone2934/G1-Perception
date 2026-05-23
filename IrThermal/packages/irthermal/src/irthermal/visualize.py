"""热成像矩阵 → BGR 伪彩色（OpenCV）。"""

from __future__ import annotations

import cv2
import numpy as np


def temps_to_bgr(temps: np.ndarray, width: int, height: int) -> np.ndarray:
    lo, hi = float(temps.min()), float(temps.max())
    span = max(hi - lo, 1e-3)
    norm = np.clip((temps - lo) / span, 0, 1)
    u8 = (norm * 255).astype(np.uint8)
    colored = cv2.applyColorMap(u8, cv2.COLORMAP_INFERNO)
    return cv2.resize(colored, (width, height), interpolation=cv2.INTER_NEAREST)
