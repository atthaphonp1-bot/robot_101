import math
from typing import List, Dict, Any, Tuple

def validate_plan(
    plan: Dict[str, Any],
    objects: List[Dict[str, Any]],
    reach: Tuple[float, float] = (60.0, 230.0),
    max_steps: int = 10,
) -> List[str]:
    """
    Validate a robot‑arm plan.

    Parameters
    ----------
    plan : dict
        Must contain a key ``"steps"`` that is a list of step dictionaries.
    objects : list of dict
        Each dict has keys ``"id"``, ``"color"``, ``"x"``, ``"y"``.
    reach : (float, float), optional
        Minimum and maximum reachable distance (mm) from the robot base.
    max_steps : int, optional
        Maximum number of allowed steps.

    Returns
    -------
    list of str
        Empty list if the plan is valid; otherwise a list of error messages.
    """
    # --------------------------------------------------------------------- #
    # 1.  Early type check for the plan structure
    # --------------------------------------------------------------------- #
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        return ["plan: steps must be a list"]

    steps = plan["steps"]
    errors: List[str] = []

    # --------------------------------------------------------------------- #
    # 2.  Length checks
    # --------------------------------------------------------------------- #
    n = len(steps)
    if n == 0:
        errors.append("plan: no steps")
    if n > max_steps:
        errors.append(f"plan: too many steps ({n} > {max_steps})")

    # --------------------------------------------------------------------- #
    # Helper structures
    # --------------------------------------------------------------------- #
    # map object id -> object dict
    obj_by_id = {obj["id"]: obj for obj in objects}

    def out_of_reach(obj_id: int) -> str | None:
        """Return an error string if object is out of reach, else None."""
        obj = obj_by_id.get(obj_id)
        if obj is None:
            return None  # caller will have already reported unknown object
        dist = math.hypot(obj["x"], obj["y"])
        if dist < reach[0] or dist > reach[1]:
            return f"object {obj_id} out of reach"
        return None

    # --------------------------------------------------------------------- #
    # 3.  Iterate over steps
    # --------------------------------------------------------------------- #
    holding = False  # whether we currently hold an object

    for idx, step in enumerate(steps, start=1):
        # ----------------------------------------------------------------- #
        # Validate step container and action name
        # ----------------------------------------------------------------- #
        if not isinstance(step, dict):
            errors.append(f"step {idx}: unknown action")
            continue

        action = step.get("action")
        if action not in {"pick", "place", "home", "grip", "stop"}:
            errors.append(f"step {idx}: unknown action")
            continue

        # ----------------------------------------------------------------- #
        # Action specific validation
        # ----------------------------------------------------------------- #
        if action == "pick":
            obj_id = step.get("object")
            if obj_id not in obj_by_id:
                errors.append(f"step {idx}: unknown object")
                # do not change holding state
                continue

            # reach check for the object to be picked
            reach_err = out_of_reach(obj_id)
            if reach_err:
                errors.append(f"step {idx}: {reach_err}")

            if holding:
                errors.append(f"step {idx}: already holding an object")
                # still do not pick another one
                continue

            # successful pick
            holding = True

        elif action == "place":
            # 1) must be holding something
            if not holding:
                errors.append(f"step {idx}: nothing to place")

            target = step.get("target")
            bad_target = False

            if not isinstance(target, dict):
                bad_target = True
            else:
                # exactly one of the allowed specifications
                keys = set(target.keys())
                if keys == {"pad"} and target.get("pad") is True:
                    pass  # pad target – nothing else to check
                elif keys == {"on"}:
                    obj_id = target["on"]
                    if obj_id not in obj_by_id:
                        errors.append(f"step {idx}: unknown object")
                    else:
                        reach_err = out_of_reach(obj_id)
                        if reach_err:
                            errors.append(f"step {idx}: {reach_err}")
                elif keys == {"near", "side"}:
                    obj_id = target["near"]
                    side = target["side"]
                    if side not in {"left", "right", "front", "back"}:
                        bad_target = True
                    else:
                        if obj_id not in obj_by_id:
                            errors.append(f"step {idx}: unknown object")
                        else:
                            reach_err = out_of_reach(obj_id)
                            if reach_err:
                                errors.append(f"step {idx}: {reach_err}")
                else:
                    bad_target = True

            if bad_target:
                errors.append(f"step {idx}: bad target")

            # After a place step we are no longer holding anything,
            # even if there were errors.
            holding = False

        elif action == "grip":
            state = step.get("state")
            if state not in {"open", "close"}:
                errors.append(f"step {idx}: bad grip state")

        # "home" and "stop" have no additional validation

    # --------------------------------------------------------------------- #
    # 4.  Final holding check
    # --------------------------------------------------------------------- #
    if holding:
        errors.append("plan: ends while holding an object")

    return errors