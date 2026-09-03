import teensy


# ---- parsing ----

def test_parses_a_current_reply():
    assert teensy.parse_servo("SERVO current pan=110 tilt=110") == (110, 110)


def test_parses_a_set_reply():
    assert teensy.parse_servo("SERVO set pan=95 tilt=120") == (95, 120)


def test_parses_a_partial_reply():
    assert teensy.parse_servo("SERVO set pan=70") == (70, None)


def test_parses_negative_values():
    assert teensy.parse_servo("SERVO set pan=-5 tilt=3") == (-5, 3)


def test_empty_line_parses_to_nothing():
    assert teensy.parse_servo("") == (None, None)
    assert teensy.parse_servo(None) == (None, None)


def test_does_not_take_numbers_from_a_heartbeat():
    hb = "HEARTBEAT seq=203 uptime_ms=203000 temp_c=52.2 bat_v=12.5"
    assert teensy.parse_servo(hb) == (None, None)


# ---- deciding which lines are answers ----

def test_heartbeat_is_not_a_servo_reply():
    assert not teensy.is_servo_reply(
        "HEARTBEAT seq=1 uptime_ms=1000 temp_c=52.2 bat_v=12.5")


def test_servo_current_is_a_reply():
    assert teensy.is_servo_reply("SERVO current pan=110 tilt=110")


def test_servo_set_is_a_reply():
    assert teensy.is_servo_reply("SERVO set pan=110 tilt=110")


def test_the_real_usage_line_is_not_a_reply():
    """The exact line the firmware prints, not a paraphrase of it.

    Bare `SERVO` prints usage first and the position second. This line starts
    with "SERVO " and contains "pan=", so a loose matcher returns the EXAMPLE
    values 90/90 as though they were the position. An earlier version of this
    test used the string "SERVO usage" and passed while the bug was live.
    """
    assert not teensy.is_servo_reply("SERVO usage: SERVO pan=90 tilt=90  (0-180)")


def test_usage_then_position_picks_the_position():
    lines = ["SERVO usage: SERVO pan=90 tilt=90  (0-180)",
             "SERVO current pan=110 tilt=110"]
    matched = [l for l in lines if teensy.is_servo_reply(l)]
    assert matched == ["SERVO current pan=110 tilt=110"]


def test_other_console_output_is_not_a_reply():
    for line in ("BOOT teensy41 microros", "PONG 12345",
                 "BATTERY main_v=12.5 raw=3100", "EVENT led=on"):
        assert not teensy.is_servo_reply(line)


# ---- the port ----

def test_port_glob_is_not_a_hardcoded_serial_number():
    """Device paths move; this project has been bitten by hardcoding three times."""
    assert "*" in teensy.PORT_GLOB
    assert not any(ch.isdigit() and len(tok) > 6
                   for tok in teensy.PORT_GLOB.split("_") for ch in tok)
