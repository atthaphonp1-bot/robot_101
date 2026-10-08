import cv2
import numpy as np

# ----------------------------------------------------------------------
# Default HSV colour ranges (OpenCV HSV: H 0‑179, S 0‑255, V 0‑255)
# ----------------------------------------------------------------------
DEFAULT_COLORS = {
    "red": [
        ((0, 100, 80), (10, 255, 255)),      # lower reds
        ((170, 100, 80), (179, 255, 255)),   # upper reds
    ],
    "yellow": [
        ((20, 100, 80), (35, 255, 255)),
    ],
    "green": [
        ((40, 100, 80), (85, 255, 255)),
    ],
    "blue": [
        ((100, 100, 80), (130, 255, 255)),
    ],
}


def _make_mask(hsv_img: np.ndarray, ranges: list) -> np.ndarray:
    """
    Build a binary mask for the supplied HSV image using one or more
    (lower, upper) HSV bounds.
    """
    mask = np.zeros(hsv_img.shape[:2], dtype=np.uint8)
    for lower, upper in ranges:
        lo = np.array(lower, dtype=np.uint8)
        hi = np.array(upper, dtype=np.uint8)
        cur = cv2.inRange(hsv_img, lo, hi)
        mask = cv2.bitwise_or(mask, cur)
    return mask


def detect_objects(
    img_bgr: np.ndarray,
    colors: dict = DEFAULT_COLORS,
    min_area: int = 150,
) -> list:
    """
    Detect coloured objects in a BGR image.

    Parameters
    ----------
    img_bgr : np.ndarray
        H×W×3 uint8 BGR image.
    colors : dict, optional
        Mapping colour name → list of (lower_hsv, upper_hsv) tuples.
        Defaults to ``DEFAULT_COLORS``.
    min_area : int, optional
        Minimum contour area to keep. Defaults to 150.

    Returns
    -------
    list of dict
        Each dict contains the keys ``color``, ``u``, ``v``,
        ``area`` and ``angle``. The list is sorted by descending area.
    """
    # Convert to HSV colour space
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # Kernel for morphological operations
    kernel = np.ones((5, 5), dtype=np.uint8)

    detections = []

    for name, ranges in colors.items():
        # Build mask for the current colour
        mask = _make_mask(hsv, ranges)

        # Clean up the mask
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Find external contours
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < min_area:
                continue

            # Centroid (u, v) from image moments
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                # Degenerate case – fall back to bounding‑box centre
                x, y, w, h = cv2.boundingRect(cnt)
                cx = float(x + w / 2)
                cy = float(y + h / 2)
            else:
                cx = float(M["m10"] / M["m00"])
                cy = float(M["m01"] / M["m00"])

            # Angle of the minimum area rectangle
            _, _, angle = cv2.minAreaRect(cnt)

            detections.append(
                {
                    "color": name,
                    "u": cx,
                    "v": cy,
                    "area": area,
                    "angle": float(angle),
                }
            )

    # Sort by area descending
    detections.sort(key=lambda d: d["area"], reverse=True)
    return detections