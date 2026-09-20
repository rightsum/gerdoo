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

-- Assigned further down, with the on-screen controls. Declared here because
-- the seek binding has to consult it: a double tap ON a button is that button
-- being pressed twice, not a request to skip.
local tap_controls

mp.add_forced_key_binding("MBTN_LEFT_DBL", "gerdoo-seek", function()
    if tap_controls and tap_controls() then return end
    seek_from_tap()
end)

-- The unit's window flags do not stick, because the window is created lazily
-- when a file loads rather than at start. Setting it per file is what actually
-- covers the kiosk face.
mp.register_event("file-loaded", function()
    mp.set_property_bool("fullscreen", true)
end)


-- ---------------------------------------------------------------------------
-- On-screen controls, drawn by mpv rather than by the kiosk page.
--
-- The page's own toolbar cannot be seen while a video plays: mpv's window owns
-- the screen. Sizing mpv to leave a strip for the page was tried and reverted —
-- it costs real estate, and xfwm4's stacking rules made it a fight (log 025).
-- Drawing the controls here instead keeps the video genuinely fullscreen and
-- floats the buttons over it.
--
-- Coordinates are self-consistent: the overlay is drawn in the same space that
-- `mouse-pos` reports, so wherever a button is painted is where a tap on it
-- lands, whatever the panel's rotation does to the axes. That is why this does
-- NOT need the AXIS/INVERT treatment the seek code above does — seek has to
-- know which side is *physically* left, and this does not.
-- ---------------------------------------------------------------------------

local FACE_URL = os.getenv("GERDOO_FACE_URL") or "http://localhost:8080"

-- Sized for a 5 inch 1080p panel (~440 PPI), where 156px is only about 9mm.
-- The wake control is a DOME sitting on the bottom edge: its flat side is the
-- screen edge, so every pixel of it is reachable and none is wasted off-screen.
local WAKE_RX   = 370     -- dome half-width  (740 across)
local WAKE_RY   = 185     -- dome height; shallow, so it rises from the
                          -- bottom edge rather than bubbling over the picture
local BTN       = 130     -- side of the square media buttons
local MARGIN    = 40
local BOTTOM    = 26      -- gap from the bottom edge, media buttons only

-- Fallback only. The real colour is the face's own, fetched below, so the
-- control matches whatever the robot currently is.
local FACE_COLOUR = "2AD4FF"

local overlay = nil
-- True between file-loaded and end-file. Needed separately from `overlay`
-- because the FIRST draw usually fails: at file-loaded the window has no size
-- yet, so osd-dimensions is 0 and there is nothing to lay out against. The
-- redraw that follows must not be gated on an overlay that was never created.
local active = false

local function buttons(w, h)
    local by = h - BOTTOM - BTN
    return {
        -- Centre is ON the bottom edge, so only the top half is on screen.
        wake  = {kind = "dome", cx = w / 2, cy = h, rx = WAKE_RX, ry = WAKE_RY},
        pause = {kind = "rect", x = MARGIN, y = by, w = BTN, h = BTN},
        stop  = {kind = "rect", x = MARGIN * 2 + BTN, y = by, w = BTN, h = BTN},
    }
end

-- Upper half of a circle, closed along its flat side: two cubic beziers over
-- the top (control points at 0.5523r, the usual circle approximation) and a
-- straight line back across the bottom.
local function ass_dome(cx, cy, rx, ry)
    local kx, ky = rx * 0.5523, ry * 0.5523
    return string.format(
        "m %d %d b %d %d %d %d %d %d b %d %d %d %d %d %d l %d %d",
        cx - rx, cy,
        cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry,
        cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy,
        cx - rx, cy)
end

local function ass_rect(x, y, w, h)
    return string.format("m %d %d l %d %d l %d %d l %d %d", x, y, x + w, y, x + w, y + h, x, y + h)
end

-- ASS alpha is inverted: 00 is opaque, FF invisible. CC is ~20% fill and 66 is
-- ~60% border, so the video stays readable straight through every control.
local ALPHA = "\\1a&HCC&\\3a&H66&\\4a&HFF&"

local function draw()
    local dim = mp.get_property_native("osd-dimensions")
    if not dim or not dim.w or dim.w == 0 then return end
    local b = buttons(dim.w, dim.h)

    if not overlay then overlay = mp.create_osd_overlay("ass-events") end
    overlay.res_x, overlay.res_y = dim.w, dim.h

    local paused = mp.get_property_bool("pause")
    local a = {}
    local function shape(colour, path)
        a[#a + 1] = string.format(
            "{\\an7\\pos(0,0)\\bord2\\shad0\\1c&H%s&\\3c&HFFFFFF&%s\\p1}%s{\\p0}",
            colour, ALPHA, path)
    end
    local function label(x, y, size, text)
        a[#a + 1] = string.format(
            "{\\an5\\pos(%d,%d)\\fs%d\\b1\\bord0\\shad0\\1c&HFFFFFF&\\1a&H20&}%s",
            x, y, size, text)
    end

    -- ASS colours are BGR, so the face's RRGGBB is reversed here.
    local bgr = FACE_COLOUR:sub(5, 6) .. FACE_COLOUR:sub(3, 4) .. FACE_COLOUR:sub(1, 2)
    shape(bgr, ass_dome(b.wake.cx, b.wake.cy, b.wake.rx, b.wake.ry))
    label(b.wake.cx, b.wake.cy - 52, 46, "Wake!")

    shape("12100E", ass_rect(b.pause.x, b.pause.y, b.pause.w, b.pause.h))
    label(b.pause.x + BTN / 2, b.pause.y + BTN / 2, 54, paused and "▶" or "❚❚")

    shape("12100E", ass_rect(b.stop.x, b.stop.y, b.stop.w, b.stop.h))
    label(b.stop.x + BTN / 2, b.stop.y + BTN / 2, 54, "■")

    overlay.data = table.concat(a, "\n")
    overlay:update()
end

local function hide()
    if overlay then overlay:remove(); overlay = nil end
end

local function post(path)
    -- Detached: a hung request must not stall playback or the input thread.
    mp.command_native_async({
        name = "subprocess", playback_only = false, capture_stdout = true,
        args = {"curl", "-s", "-m", "5", "-X", "POST", FACE_URL .. path},
    }, function() end)
end

local function hit(pos, b)
    if b.kind == "dome" then
        -- Ellipse test. The half below the screen edge cannot be tapped
        -- anyway, so there is no need to exclude it.
        local dx = (pos.x - b.cx) / b.rx
        local dy = (pos.y - b.cy) / b.ry
        return dx * dx + dy * dy <= 1
    end
    return pos.x >= b.x and pos.x <= b.x + b.w
       and pos.y >= b.y and pos.y <= b.y + b.h
end

-- Returns true when the tap was consumed by a control, so the seek handler can
-- ignore it: tapping "stop" must not also count as a seek.
tap_controls = function()
    local pos = mp.get_property_native("mouse-pos")
    local dim = mp.get_property_native("osd-dimensions")
    if not pos or not dim or not dim.w then return false end
    local b = buttons(dim.w, dim.h)

    if hit(pos, b.wake) then
        -- Only starts the session. The server stops the video and replays it
        -- afterwards on its own (_video_yield_to_call in app.py), so this must
        -- NOT also pause or stop anything.
        post("/api/voice/wake")
        mp.osd_message("waking…", 1.5)
        return true
    end
    if hit(pos, b.pause) then
        mp.set_property_bool("pause", not mp.get_property_bool("pause"))
        draw()
        return true
    end
    if hit(pos, b.stop) then
        post("/api/video/stop")
        return true
    end
    return false
end

mp.add_forced_key_binding("MBTN_LEFT", "gerdoo-controls", tap_controls)

-- Ask the face what colour it currently is, so the control matches it. Async:
-- a slow or dead server must not hold up playback, and the fallback above is
-- already on screen by then.
local function refresh_colour()
    mp.command_native_async({
        name = "subprocess", playback_only = false, capture_stdout = true,
        args = {"curl", "-s", "-m", "3", FACE_URL .. "/api/state"},
    }, function(ok, res)
        if not ok or not res or not res.stdout then return end
        local hex = res.stdout:match('"color"%s*:%s*"#(%x%x%x%x%x%x)"')
        if hex and hex:upper() ~= FACE_COLOUR then
            FACE_COLOUR = hex:upper()
            if active then draw() end
        end
    end)
end

mp.register_event("file-loaded", function() active = true; refresh_colour(); draw() end)
mp.register_event("end-file", function() active = false; hide() end)
mp.observe_property("pause", "bool", function() if active then draw() end end)
mp.observe_property("osd-dimensions", "native", function() if active then draw() end end)
