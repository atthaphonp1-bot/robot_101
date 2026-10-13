import cv2
import numpy as np


def annotate(img_bgr: np.ndarray,
             objects: list,
             radius: int = 14) -> np.ndarray:
    """
    Draw numbered markers on a copy of an image.

    Parameters
    ----------
    img_bgr : np.ndarray
        H×W×3 uint8 BGR image.  It is **not** modified.
    objects : list of dict
        Each dict has keys ``"id"``, ``"u"``, ``"v"``.  ``u`` and ``v`` are the
        (float) pixel coordinates of the object centre.
    radius : int, optional
        Radius of the marker circles (default 14).

    Returns
    -------
    np.ndarray
        A new H×W×3 uint8 image with the markers drawn.
    """
    # Work on a copy – the original must stay unchanged.
    out = img_bgr.copy()

    # Nothing to draw?
    if not objects:
        return out

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_thick = 1
    black = (0, 0, 0)
    white = (255, 255, 255)

    for obj in objects:
        # integer pixel centre (x, y) = (u, v)
        cx = int(round(obj["u"]))
        cy = int(round(obj["v"]))
        centre = (cx, cy)

        # filled black circle
        cv2.circle(out, centre, radius, black, -1, cv2.LINE_AA)

        # white ring (thickness = 2)
        cv2.circle(out, centre, radius, white, 2, cv2.LINE_AA)

        # put the id as white text centred on the circle
        text = str(obj["id"])
        (txt_w, txt_h), baseline = cv2.getTextSize(
            text, font, font_scale, font_thick
        )
        # bottom‑left corner so that the text box is centred
        text_x = cx - txt_w // 2
        text_y = cy + txt_h // 2
        cv2.putText(
            out,
            text,
            (text_x, text_y),
            font,
            font_scale,
            white,
            font_thick,
            cv2.LINE_AA,
        )

    return out