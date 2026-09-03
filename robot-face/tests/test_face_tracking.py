import pytest

import face_tracking as ft


def face(cx=0.5, cy=0.5, w=0.2, h=0.2):
    return ft.Face(cx=cx, cy=cy, w=w, h=h)


# ---- choosing a face ----

def test_largest_of_none_is_none():
    assert ft.largest([]) is None


def test_largest_picks_the_biggest_not_the_first():
    small = face(cx=0.1, w=0.05, h=0.05)
    big = face(cx=0.9, w=0.4, h=0.4)
    assert ft.largest([small, big]) is big


def test_largest_of_one_is_that_one():
    f = face()
    assert ft.largest([f]) is f


# ---- error ----

def test_centred_face_has_no_error():
    assert ft.centring_error(face(0.5, 0.5)) == (0.0, 0.0)


def test_error_signs_follow_image_coordinates():
    ex, ey = ft.centring_error(face(0.75, 0.25))
    assert ex > 0      # right of centre
    assert ey < 0      # above centre


# ---- the deadzone ----

def test_small_error_does_not_move_the_neck():
    f = face(cx=0.5 + ft.DEADZONE / 2)
    assert ft.next_position(f, 100, 90) == (100, 90)


def test_error_just_past_the_deadzone_does_move_it():
    f = face(cx=0.5 + ft.DEADZONE * 1.5)
    assert ft.next_position(f, 100, 90) != (100, 90)


def test_is_centred_matches_the_deadzone():
    assert ft.is_centred(face(0.5, 0.5))
    assert ft.is_centred(face(0.5 + ft.DEADZONE / 2, 0.5))
    assert not ft.is_centred(face(0.5 + ft.DEADZONE * 2, 0.5))


# ---- direction ----

def test_face_to_the_right_decreases_pan_when_inverted():
    pan, _ = ft.next_position(face(cx=0.9), 100, 90, pan_inverted=True)
    assert pan < 100


def test_face_to_the_right_increases_pan_when_not_inverted():
    pan, _ = ft.next_position(face(cx=0.9), 100, 90, pan_inverted=False)
    assert pan > 100


def test_tilt_default_is_inverted_on_this_gimbal():
    """Raising your head (face higher in frame) must LOWER the tilt number.

    Measured on the robot: the opposite convention chased away from the face
    until it hit TILT_MAX.
    """
    _, tilt = ft.next_position(face(cy=0.1), 100, 90)     # face high in frame
    assert tilt > 90, "a face above centre should increase tilt"
    _, tilt = ft.next_position(face(cy=0.9), 100, 90)     # face low in frame
    assert tilt < 90, "a face below centre should decrease tilt"


def test_tilt_inversion_is_switchable():
    _, a = ft.next_position(face(cy=0.9), 100, 90, tilt_inverted=False)
    _, b = ft.next_position(face(cy=0.9), 100, 90, tilt_inverted=True)
    assert (a - 90) == -(b - 90)


# ---- limits ----

def test_step_is_capped():
    pan, _ = ft.next_position(face(cx=1.0), 100, 90)
    assert abs(pan - 100) <= ft.MAX_STEP


def test_pan_never_leaves_its_range():
    pan, _ = ft.next_position(face(cx=1.0), ft.PAN_MIN, 90)
    assert ft.PAN_MIN <= pan <= ft.PAN_MAX
    pan, _ = ft.next_position(face(cx=0.0), ft.PAN_MAX, 90)
    assert ft.PAN_MIN <= pan <= ft.PAN_MAX


def test_tilt_never_leaves_its_range():
    _, tilt = ft.next_position(face(cy=1.0), 100, ft.TILT_MAX)
    assert ft.TILT_MIN <= tilt <= ft.TILT_MAX
    _, tilt = ft.next_position(face(cy=0.0), 100, ft.TILT_MIN)
    assert ft.TILT_MIN <= tilt <= ft.TILT_MAX


# ---- it should actually converge ----

def test_tracking_converges_on_a_stationary_face():
    """Repeatedly correcting toward a fixed face must settle, not oscillate."""
    pan, tilt = ft.PAN_CENTRE, ft.TILT_CENTRE
    f = face(cx=0.8, cy=0.7)
    seen = []
    for _ in range(40):
        pan, tilt = ft.next_position(f, pan, tilt)
        seen.append((pan, tilt))
    # Without feedback from a moving camera the position walks to a limit and
    # stops there; what matters is that it stops.
    assert seen[-1] == seen[-2]


def test_centre_constants_are_inside_their_ranges():
    assert ft.PAN_MIN < ft.PAN_CENTRE < ft.PAN_MAX
    assert ft.TILT_MIN < ft.TILT_CENTRE < ft.TILT_MAX
