# -*- coding: utf-8 -*-

# colour vocab (module level, as requested)
COLOR_WORDS = {
    "red":    ["แดง", "red"],
    "blue":   ["น้ำเงิน", "ฟ้า", "blue"],
    "yellow": ["เหลือง", "yellow"],
}

# ----------------------------------------------------------------------
def _first_obj_of_color(objects, colour):
    """Return the object dict with the smallest id that has the given colour,
    or None if no such object exists."""
    candidates = [obj for obj in objects if obj.get("color") == colour]
    return min(candidates, key=lambda o: o["id"]) if candidates else None


def mock_plan(text, objects):
    """
    Very small rule‑based stand‑in for a vision‑language model.

    Parameters
    ----------
    text : str
        Command in Thai or English.
    objects : list[dict]
        List of objects, each with at least ``id`` (int) and ``color`` (str).

    Returns
    -------
    dict
        {"say": str, "steps": list}
    """
    t = text.lower()

    # --------------------------------------------------------------
    # 1. find mentioned colours and their first occurrence positions
    colour_positions = []
    for colour, words in COLOR_WORDS.items():
        pos = None
        for w in words:
            p = t.find(w.lower())
            if p >= 0 and (pos is None or p < pos):
                pos = p
        if pos is not None:
            colour_positions.append((pos, colour))

    # order by earliest appearance
    colour_positions.sort(key=lambda x: x[0])
    mentioned_colours = [c for _, c in colour_positions]

    # --------------------------------------------------------------
    # 2. no colour mentioned → handle generic commands
    if not mentioned_colours:
        if any(k in t for k in ("กลับ", "home", "เริ่มต้น")):
            return {"say": "กลับท่าเริ่มต้น", "steps": [{"action": "home"}]}
        if any(k in t for k in ("หยุด", "stop")):
            return {"say": "หยุด", "steps": [{"action": "stop"}]}
        return {"say": "ไม่เข้าใจคำสั่ง", "steps": []}

    # --------------------------------------------------------------
    # 3. first colour → object to pick
    c1 = mentioned_colours[0]
    obj1 = _first_obj_of_color(objects, c1)
    if not obj1:
        return {"say": f"ไม่พบวัตถุสี {c1}", "steps": []}
    id1 = obj1["id"]

    # --------------------------------------------------------------
    # 4. decide where to place the object
    target = {"pad": True}                     # default

    # a) a second colour exists and refers to a *different* object
    if len(mentioned_colours) >= 2:
        c2 = mentioned_colours[1]
        obj2 = _first_obj_of_color(objects, c2)
        if obj2 and obj2["id"] != id1:
            # i) check for “on top / onto”
            if any(k in t for k in ("บน", "ซ้อน", "on top", "onto")):
                target = {"on": obj2["id"]}
            else:
                # ii) side word (first found in the prescribed order)
                side_map = [
                    ("ซ้าย", "left"),
                    ("ขวา", "right"),
                    ("หน้า", "front"),
                    ("หลัง", "back"),
                ]
                side = "right"                     # default if nothing matches
                for thai, eng in side_map:
                    if thai in t or eng in t:
                        side = eng
                        break
                target = {"near": obj2["id"], "side": side}

    # --------------------------------------------------------------
    # 5. build result
    result = {
        "say": f"หยิบ #{id1} ({c1}) แล้ววาง",
        "steps": [
            {"action": "pick", "object": id1},
            {"action": "place", "target": target},
            {"action": "home"},
        ],
    }
    return result