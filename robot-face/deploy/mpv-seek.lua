-- Double-tap the screen to skip: one side forward, the other back.
--
-- This lives inside mpv rather than in the kiosk web page for one reason: while
-- a video plays, mpv's window owns the screen, so the page never sees the touch.
-- The touchscreen is an ordinary X pointer, so a tap arrives here as MBTN_LEFT.
--
-- The panel is mounted rotated (xrandr "right"), and a touchscreen does not
-- necessarily get rotated in step with the display — so the framebuffer axis that
-- corresponds to "physically left and right" is not obvious, and guessing it wrong
-- means seeking backward when you meant forward. Hence AXIS/INVERT below and the
-- on-screen readout: tap once, read what it says, set the two constants.

local SECONDS = 10

-- Which framebuffer axis runs physically left-to-right across the screen.
-- "y" is the starting guess: with the display rotated right, the framebuffer's
-- y axis runs along the screen's physical width.
local AXIS = "y"

-- true when a LARGER value on that axis means physically further LEFT.
-- Rotating right maps increasing framebuffer y to physically leftward.
local INVERT = true

-- Set true while calibrating: every tap reports where it landed, so the two
-- constants above can be fixed from evidence rather than reasoning.
local SHOW_TAP = true

local function seek_from_tap()
    local pos = mp.get_property_native("mouse-pos")
    local dim = mp.get_property_native("osd-dimensions")
    if not pos or not dim then
        mp.osd_message("seek: no pointer position", 2)
        return
    end

    local value, extent
    if AXIS == "y" then
        value, extent = pos.y, dim.h
    else
        value, extent = pos.x, dim.w
    end
    if not value or not extent or extent == 0 then
        return
    end

    -- Past the midpoint is one side of the screen, before it the other.
    local past_middle = value > (extent / 2)
    if INVERT then
        past_middle = not past_middle
    end
    local delta = past_middle and SECONDS or -SECONDS

    mp.commandv("seek", tostring(delta), "relative")

    if SHOW_TAP then
        mp.osd_message(string.format("tap x=%d y=%d  of %dx%d  ->  %+ds",
                                     pos.x or -1, pos.y or -1,
                                     dim.w or -1, dim.h or -1, delta), 3)
    else
        mp.osd_message(string.format("%+ds", delta), 1)
    end
end

mp.add_forced_key_binding("MBTN_LEFT_DBL", "gerdoo-seek", seek_from_tap)

-- The unit's window flags do not stick, because the window is created lazily
-- when a file loads rather than at start. Fullscreen in particular has to be
-- cleared per file, or an earlier session's state carries over.
--
-- Deliberately NOT fullscreen: the bottom strip belongs to the kiosk toolbar.
-- The SIZE comes from --geometry in video-player.service, not from here —
-- display-width/display-height are nil at file-loaded, because the window does
-- not exist yet.
mp.register_event("file-loaded", function()
    mp.set_property_bool("fullscreen", false)
end)
