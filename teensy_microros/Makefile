# Teensy 4.1 bring-up — builds and flashes ON THE JETSON.
#
# The Teensy hangs off the Jetson's USB, so the toolchain lives there too.
# That is also the long-term shape: the robot rebuilds its own firmware
# without a laptop in the loop.
#
# Usage (on the Jetson):
#   make compile   - build only
#   make upload    - build & flash  (fully headless)
#   make health    - one-shot PING/INFO/HEALTH probe
#   make monitor   - health check + 10s heartbeat watch
#   make ports     - show what is detected and in which USB mode
#   make clean
#
# Three things this file works around, all learned the hard way — see logs/003:
#   1. usb=serial must be pinned in the FQBN or the board can land in RawHID,
#      where no /dev/ttyACM* can ever appear.
#   2. Flashing uses teensy_loader_cli, NOT arduino-cli upload. arduino-cli
#      delegates to teensy_post_compile, which does not flash — it messages the
#      Teensy Loader GUI, which is GTK and dies headless. See logs/005.
#   3. /dev/ttyACM<N> is NOT stable — observed moving 0 -> 1 -> 0 with nothing
#      unplugged. Always address the board by its by-id serial-number symlink.

FQBN  := teensy:avr:teensy41:usb=serial2,speed=600,opt=o2std,keys=en-us
BAUD  := 115200
MCU   := TEENSY41

BUILD_DIR := $(CURDIR)/build
ACLI      := $(shell command -v arduino-cli 2>/dev/null || echo $$HOME/.local/bin/arduino-cli)
TLOADER   := $(shell command -v teensy_loader_cli 2>/dev/null || echo $$HOME/.local/bin/teensy_loader_cli)

# arduino-cli emits "<sketch>.ino.hex". Derive the name from the sketch actually
# present so renaming the directory cannot break the flash step.
SKETCH := $(notdir $(firstword $(wildcard $(CURDIR)/*.ino)))
HEX    := $(BUILD_DIR)/$(SKETCH).hex

# Stable name, keyed on the board's own serial number. Survives re-enumeration
# and tells two Teensys apart once the arm controller is added. Falls back to
# the raw node only so error messages stay useful.
PORT ?= $(shell ls /dev/serial/by-id/usb-Teensyduino_*Serial_*-if00 2>/dev/null | head -n 1)
ifeq ($(PORT),)
  PORT := $(shell ls /dev/ttyACM* 2>/dev/null | head -n 1)
endif

.PHONY: all compile upload monitor health ports clean info

all: upload health

compile:
	@echo "=== Compiling for $(FQBN) ==="
	$(ACLI) compile --fqbn $(FQBN) --output-dir $(BUILD_DIR) .

# -s soft-reboots a running board into its bootloader over USB, so no PROGRAM
# button press is needed. That works only because the PJRC udev rules are
# installed (/etc/udev/rules.d/00-teensy.rules) — without them the bootloader
# is root-only and this silently waits forever.
# -w waits for the board to appear; the timeout stops that becoming a hang.
upload: compile
	@test -f $(HEX) || { echo "No hex at $(HEX)"; exit 1; }
	@echo "=== Flashing $(notdir $(HEX)) ==="
	timeout 90 $(TLOADER) --mcu=$(MCU) -w -s -v $(HEX)
	@echo "=== Waiting for re-enumeration ==="
	@sleep 6
	@$(MAKE) --no-print-directory ports

ports:
	@echo "=== USB mode ==="
	@lsusb | grep -i "16c0" || echo "  no Teensy on USB"
	@echo "  0483=Serial  048b=Dual Serial  0486=RawHID (RawHID has no tty at all)"
	@echo "=== stable name (use this everywhere) ==="
	@ls -l /dev/serial/by-id/ 2>/dev/null | grep -i teensy || echo "  none — board is not in Serial mode"
	@echo "=== raw nodes (unstable, do not hardcode) ==="
	@ls -l /dev/ttyACM* 2>/dev/null || echo "  none"

health:
	@test -n "$(PORT)" || { echo "No serial port. Board is probably in RawHID — run 'make ports'."; exit 1; }
	@python3 health_check.py --port $(PORT) --baud $(BAUD)

monitor:
	@test -n "$(PORT)" || { echo "No serial port. Board is probably in RawHID — run 'make ports'."; exit 1; }
	@python3 health_check.py --port $(PORT) --baud $(BAUD) --monitor 10

clean:
	rm -rf $(BUILD_DIR)

info:
	@echo "FQBN    : $(FQBN)"
	@echo "SKETCH  : $(SKETCH)"
	@echo "HEX     : $(HEX)"
	@echo "PORT    : $(PORT)"
	@echo "BAUD    : $(BAUD)"
	@echo "ACLI    : $(ACLI)"
	@echo "TLOADER : $(TLOADER)"
