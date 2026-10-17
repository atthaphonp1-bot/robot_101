import math
from typing import Any, List, Optional, Dict

def check_objects(objects: Any, max_objects: int = 50) -> Optional[str]:
    """
    Validate a list of detected objects for the robot planner.

    Parameters
    ----------
    objects : any
        The value that should be a list of dicts.
    max_objects : int, optional
        Maximum allowed number of objects (default 50).

    Returns
    -------
    None if the list is valid, otherwise a short English error string.
    """
    # 1. objects must be a list
    if not isinstance(objects, list):
        return "objects must be a list"

    # 2. too many objects
    if len(objects) > max_objects:
        return f"too many objects (max {max_objects})"

    # collect ids to later detect duplicates
    seen_ids = set()

    for i, item in enumerate(objects):
        # 3. each entry must be a dict (object)
        if not isinstance(item, dict):
            return f"objects[{i}] must be an object"

        # 4. id must exist and be an int (but not a bool)
        if "id" not in item or not isinstance(item["id"], int) or isinstance(item["id"], bool):
            return f"objects[{i}].id must be an integer"
        obj_id = item["id"]

        # 5. x must exist and be a finite number (int/float, not bool)
        if "x" not in item:
            return f"objects[{i}].x must be a number"
        x = item["x"]
        if (not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x)):
            return f"objects[{i}].x must be a number"

        # 5. y must exist and be a finite number (int/float, not bool)
        if "y" not in item:
            return f"objects[{i}].y must be a number"
        y = item["y"]
        if (not isinstance(y, (int, float)) or isinstance(y, bool) or not math.isfinite(y)):
            return f"objects[{i}].y must be a number"

        # store id for duplicate check
        if obj_id in seen_ids:
            # duplicate detection is performed after all per‑item checks,
            # but we can early‑return here as it is the first duplicate encountered.
            return f"duplicate id {obj_id}"
        seen_ids.add(obj_id)

    # 6. duplicate ids (already handled in the loop; this is a safeguard)
    # (If we had postponed the duplicate test until after the loop,
    # we would iterate over `seen_ids` here.)

    return None