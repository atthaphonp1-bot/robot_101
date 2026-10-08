def pick_place_commands(obj_x, obj_y, place_x, place_y, place_z=17, obj_z=15, hover=110,
                        open_grip=101.7, close_grip=37.5, pitch=-90):
    # Round all coordinate-like inputs to one decimal place
    obj_x_r = round(obj_x, 1)
    obj_y_r = round(obj_y, 1)
    obj_z_r = round(obj_z, 1)
    place_x_r = round(place_x, 1)
    place_y_r = round(place_y, 1)
    place_z_r = round(place_z, 1)
    hover_r = round(hover, 1)
    # Compute hover2 and round it
    hover2 = max(hover_r, place_z_r + 60)
    hover2_r = round(hover2, 1)
    # Round grip values and pitch (though they are already at most one decimal)
    open_grip_r = round(open_grip, 1)
    close_grip_r = round(close_grip, 1)
    pitch_r = round(pitch, 1)

    return [
        {"grip": open_grip_r},
        {"ik": [obj_x_r, obj_y_r, hover_r, pitch_r]},
        {"ik": [obj_x_r, obj_y_r, obj_z_r, pitch_r]},
        {"grip": close_grip_r},
        {"ik": [obj_x_r, obj_y_r, hover_r, pitch_r]},
        {"ik": [place_x_r, place_y_r, hover2_r, pitch_r]},
        {"ik": [place_x_r, place_y_r, place_z_r, pitch_r]},
        {"grip": open_grip_r},
        {"ik": [place_x_r, place_y_r, hover2_r, pitch_r]},
    ]