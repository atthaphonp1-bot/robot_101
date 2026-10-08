"""Calibration utilities – homography estimation without OpenCV.

The module implements:
* compute_homography – DLT solution for a 2‑D → 2‑D homography.
* pixel_to_robot   – apply the homography to a single pixel.
* save_calibration – store the matrix in a JSON file.
* load_calibration – read the matrix back from JSON.
"""

import json
import numpy as np
from typing import List, Tuple, Sequence


def compute_homography(
    px_pts: Sequence[Tuple[float, float]],
    robot_pts: Sequence[Tuple[float, float]],
) -> np.ndarray:
    """
    Compute the 3×3 homography H that maps pixel coordinates (u, v)
    to robot coordinates (x, y) using the Direct Linear Transform (DLT).

    Parameters
    ----------
    px_pts : sequence of (u, v)
        Pixel coordinates. Must contain at least four points.
    robot_pts : sequence of (x, y)
        Corresponding robot coordinates. Same length as ``px_pts``.

    Returns
    -------
    H : np.ndarray, shape (3, 3), dtype float
        Normalised homography matrix (H[2,2] == 1).

    Raises
    ------
    ValueError
        If the number of points is less than four or the two input
        sequences have different lengths.
    """
    if len(px_pts) != len(robot_pts):
        raise ValueError("Pixel and robot point lists must have the same length.")
    if len(px_pts) < 4:
        raise ValueError("At least four point correspondences are required.")

    # Build the linear system A·h = 0
    rows = []
    for (u, v), (x, y) in zip(px_pts, robot_pts):
        # first row for this correspondence
        rows.append([-u, -v, -1, 0, 0, 0, x * u, x * v, x])
        # second row for this correspondence
        rows.append([0, 0, 0, -u, -v, -1, y * u, y * v, y])

    A = np.asarray(rows, dtype=float)

    # Solve with SVD: the solution is the right singular vector
    # corresponding to the smallest singular value (last row of V^T)
    _, _, Vt = np.linalg.svd(A)
    h = Vt[-1]                       # shape (9,)

    H = h.reshape(3, 3)

    # Normalise so that H[2,2] == 1 (unless it is zero – which would be singular)
    if np.isclose(H[2, 2], 0):
        raise ValueError("Degenerate configuration – cannot normalise homography.")
    H = H / H[2, 2]

    return H.astype(float)


def pixel_to_robot(H: np.ndarray, u: float, v: float) -> Tuple[float, float]:
    """
    Transform a single pixel coordinate (u, v) into robot space using homography H.

    Parameters
    ----------
    H : np.ndarray, shape (3, 3)
        Homography matrix obtained from ``compute_homography``.
    u, v : float
        Pixel coordinates.

    Returns
    -------
    (x, y) : tuple of float
        Corresponding robot coordinates.
    """
    pt_h = np.dot(H, np.array([u, v, 1.0], dtype=float))
    if np.isclose(pt_h[2], 0):
        raise ValueError("Homogeneous coordinate is zero after transformation.")
    x = pt_h[0] / pt_h[2]
    y = pt_h[1] / pt_h[2]
    return float(x), float(y)


def save_calibration(path: str, H: np.ndarray) -> None:
    """
    Save the homography matrix to a JSON file.

    The file will contain a single key ``"H"`` whose value is a nested
    Python list (3×3) representing the matrix.

    Parameters
    ----------
    path : str
        Destination file path.
    H : np.ndarray, shape (3, 3)
        Homography matrix to be saved.
    """
    data = {"H": H.tolist()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_calibration(path: str) -> np.ndarray:
    """
    Load a homography matrix saved by :func:`save_calibration`.

    Parameters
    ----------
    path : str
        Path to the JSON file.

    Returns
    -------
    H : np.ndarray, shape (3, 3), dtype float
        The loaded homography matrix.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return np.array(data["H"], dtype=float)


__all__ = [
    "compute_homography",
    "pixel_to_robot",
    "save_calibration",
    "load_calibration",
]