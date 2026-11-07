"""
Driver for the reactor screen: a Waveshare 1.69" IPS LCD (ST7789V2, 240x280), wired
straight to the Jetson's 40-pin header (inventory.md, 1.69" LCD section):

    VCC 17 (3.3 V)  GND 20  DIN 19  CLK 23  CS 24   -> SPI0, /dev/spidev0.0
    DC 29 (PQ.05)   RST 31 (PQ.06)  BL 32 (PG.06)   -> gpiochip0 lines 105, 106, 41

Pins 19/23/24 are SPI only after jetson-io's "spi1" overlay (see inventory). The GPIOs
are driven through the kernel's character device with the v1 line-handle ioctls, so
nothing beyond spidev is needed: Jetson.GPIO can't identify this board, and the
libgpiod Python bindings aren't installed.

    python3 lcd169.py test     # colour bars, then a labelled orientation card
"""

import fcntl
import os
import struct
import sys
import time

import spidev

WIDTH, HEIGHT = 240, 280
ROW_OFFSET = 20          # the 280 visible rows sit 20 rows into the ST7789's 320-row RAM

GPIOCHIP = "/dev/gpiochip0"
LINE_DC, LINE_RST, LINE_BL = 105, 106, 41

SPI_BUS, SPI_DEV = 0, 0
# The jumper wires to the header carry 8 MHz cleanly and turn the picture to static at
# 10 MHz and up (tested 2026-10-29, log 047), and streaming at 8 MHz still glitched now and
# then: 6 MHz leaves margin. The board's 40-pin header goes through auto-direction level
# shifters, which are weak drivers for long wires. A full frame takes ~180 ms, which is why
# the reactor sends only what changed.
SPI_HZ = int(os.environ.get("REACTOR_SPI_HZ", 6_000_000))

# linux/gpio.h, v1 uAPI
_GET_LINEHANDLE = 0xC16CB403     # _IOWR(0xB4, 0x03, struct gpiohandle_request), 364 bytes
_SET_LINE_VALUES = 0xC040B409    # _IOWR(0xB4, 0x09, struct gpiohandle_data), 64 bytes
_REQUEST_OUTPUT = 1 << 1


class _Line:
    """One GPIO output line, held for as long as the object lives."""

    def __init__(self, chip_fd, offset, label, value=0):
        req = bytearray(364)
        struct.pack_into("I", req, 0, offset)            # lineoffsets[0]
        struct.pack_into("I", req, 256, _REQUEST_OUTPUT)  # flags
        req[260] = 1 if value else 0                      # default_values[0]
        name = label.encode()[:31]
        req[324:324 + len(name)] = name                   # consumer_label
        struct.pack_into("I", req, 356, 1)                # lines
        fcntl.ioctl(chip_fd, _GET_LINEHANDLE, req, True)
        self.fd = struct.unpack_from("i", req, 360)[0]
        self._buf = bytearray(64)

    def set(self, value):
        self._buf[0] = 1 if value else 0
        fcntl.ioctl(self.fd, _SET_LINE_VALUES, self._buf, True)

    def close(self):
        os.close(self.fd)


# Waveshare's init for the 1.69" module (porch, gate, VCOM, power and gamma tuned for this
# panel); then column-major off, 16-bit colour, inversion on (IPS), wake, display on.
_INIT = [
    (0x36, [0x00]), (0x3A, [0x05]),
    (0xB2, [0x0B, 0x0B, 0x00, 0x33, 0x35]), (0xB7, [0x11]), (0xBB, [0x35]),
    (0xC0, [0x2C]), (0xC2, [0x01]), (0xC3, [0x0D]), (0xC4, [0x20]), (0xC6, [0x13]),
    (0xD0, [0xA4, 0xA1]), (0xD6, [0xA1]),
    (0xE0, [0xF0, 0x06, 0x0B, 0x0A, 0x09, 0x26, 0x29, 0x33, 0x41, 0x18, 0x16, 0x15, 0x29, 0x2D]),
    (0xE1, [0xF0, 0x04, 0x08, 0x08, 0x07, 0x03, 0x28, 0x32, 0x40, 0x3B, 0x19, 0x18, 0x2A, 0x2E]),
    (0xE4, [0x25, 0x00, 0x00]),
    (0x21, []),
]


class LCD:
    def __init__(self, spi_hz=SPI_HZ):
        self._chip = os.open(GPIOCHIP, os.O_RDWR)
        self.dc = _Line(self._chip, LINE_DC, "reactor-dc")
        self.rst = _Line(self._chip, LINE_RST, "reactor-rst", 1)
        self.bl = _Line(self._chip, LINE_BL, "reactor-bl")
        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEV)
        self.spi.mode = 0
        self.spi.max_speed_hz = spi_hz
        self._init()

    def _cmd(self, c, data=()):
        self.dc.set(0)
        self.spi.writebytes([c])
        if data:
            self.dc.set(1)
            self.spi.writebytes(list(data))

    def _init(self):
        for v, wait in ((1, .01), (0, .01), (1, .12)):
            self.rst.set(v)
            time.sleep(wait)
        for c, data in _INIT:
            self._cmd(c, data)
        self._cmd(0x11)              # sleep out
        time.sleep(.12)
        self._cmd(0x29)              # display on
        self.backlight(True)

    def refresh_config(self):
        """Re-send the settings a corrupted byte could have changed: colour format, scan order,
        inversion, normal mode, awake, display on. Cheap, and a glitch can't stick."""
        self._cmd(0x3A, [0x05])
        self._cmd(0x36, [0x00])
        self._cmd(0x21)
        self._cmd(0x13)
        self._cmd(0x11)
        time.sleep(.005)
        self._cmd(0x29)

    def backlight(self, on):
        self.bl.set(1 if on else 0)

    def show(self, rgb565):
        """One full frame: WIDTH*HEIGHT big-endian RGB565 pixels, as bytes."""
        self.show_region(0, 0, WIDTH - 1, HEIGHT - 1, rgb565)

    def show_region(self, x0, y0, x1, y1, rgb565):
        """The inclusive rectangle x0..x1, y0..y1, row by row, as big-endian RGB565 bytes."""
        x0, x1 = int(x0), int(x1)                 # spidev wants plain ints, not numpy's
        y0, y1 = int(y0) + ROW_OFFSET, int(y1) + ROW_OFFSET
        self._cmd(0x2A, [x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self._cmd(0x2B, [y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self._cmd(0x2C)
        self.dc.set(1)
        self.spi.writebytes2(rgb565)   # chunked to the driver's 4 KB transfers

    def close(self):
        self.backlight(False)
        self.spi.close()
        for line in (self.dc, self.rst, self.bl):
            line.close()
        os.close(self._chip)


def to_rgb565(rgb):
    """uint8 or float (0..1) HxWx3 array -> big-endian RGB565 bytes."""
    import numpy as np
    a = np.asarray(rgb)
    if a.dtype != np.uint8:
        a = (np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)
    r, g, b = a[..., 0].astype(np.uint16), a[..., 1].astype(np.uint16), a[..., 2].astype(np.uint16)
    return (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)).astype(">u2").tobytes()


def _test():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    lcd = LCD()
    try:
        for name, colour in (("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255)), ("white", (255, 255, 255))):
            frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
            frame[:] = colour
            t = time.time()
            lcd.show(to_rgb565(frame))
            print(f"{name:6s} frame sent in {(time.time() - t) * 1000:.1f} ms")
            time.sleep(1.2)
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 18, 30))
        d = ImageDraw.Draw(img)
        big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        d.rectangle([0, 0, WIDTH - 1, HEIGHT - 1], outline=(56, 217, 255), width=3)
        d.text((WIDTH // 2, 18), "TOP", font=big, fill=(255, 255, 255), anchor="mt")
        d.text((WIDTH // 2, HEIGHT // 2), "GERDOO", font=big, fill=(56, 217, 255), anchor="mm")
        d.text((8, HEIGHT - 26), "left", font=small, fill=(255, 176, 0))
        d.text((WIDTH - 8, HEIGHT - 26), "right", font=small, fill=(60, 242, 160), anchor="ra")
        lcd.show(to_rgb565(np.array(img)))
        print("orientation card shown; it stays until the next program drives the screen")
    finally:
        lcd.spi.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        _test()
    else:
        print(__doc__)
