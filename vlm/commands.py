def plan_to_commands(plan, objects, pad=(30.0, 170.0), cube=30.0, near_gap=45.0, open_grip=101.7, close_grip=37.5, hover=110.0, pitch=-90):
    r = lambda v: round(float(v), 1)
    commands = []
    pad_count = 0

    for step in plan["steps"]:
        action = step["action"]

        if action == "pick":
            obj_id = step["object"]
            obj = next(obj for obj in objects if obj["id"] == obj_id)
            x, y = obj["x"], obj["y"]
            commands.extend([
                {"grip": open_grip},
                {"ik": [r(x), r(y), r(hover), pitch]},
                {"ik": [r(x), r(y), r(cube / 2), pitch]},
                {"grip": close_grip},
                {"ik": [r(x), r(y), r(hover), pitch]}
            ])

        elif action == "place":
            target = step["target"]
            if "pad" in target:
                tx, ty = pad
                tz = cube / 2 + 2 + cube * pad_count
                pad_count += 1
            elif "on" in target:
                obj_id = target["on"]
                obj = next(obj for obj in objects if obj["id"] == obj_id)
                tx, ty = obj["x"], obj["y"]
                tz = cube * 1.5 + 2
            elif "near" in target:
                obj_id = target["near"]
                side = target["side"]
                obj = next(obj for obj in objects if obj["id"] == obj_id)
                tx, ty = obj["x"], obj["y"]
                if side == "left":
                    ty += near_gap
                elif side == "right":
                    ty -= near_gap
                elif side == "front":
                    tx += near_gap
                elif side == "back":
                    tx -= near_gap
                tz = cube / 2 + 2

            h2 = max(hover, tz + 60)
            commands.extend([
                {"ik": [r(tx), r(ty), r(h2), pitch]},
                {"ik": [r(tx), r(ty), r(tz), pitch]},
                {"grip": open_grip},
                {"ik": [r(tx), r(ty), r(h2), pitch]}
            ])

        elif action == "home":
            commands.append({"home": 1})

        elif action == "grip":
            state = step["state"]
            commands.append({"grip": open_grip if state == "open" else close_grip})

        elif action == "stop":
            commands.append({"stop": 1})

    return commands