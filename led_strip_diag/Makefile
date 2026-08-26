# LED strip bench test — builds and flashes ON THE JETSON.
#
# Mirrors teensy_microros/Makefile. Same FQBN (usb=serial2) so the board keeps
# its Dual Serial identity and the by-id paths do not move between flashes.
#
#   make upload   - build & flash
#   make watch    - dump the console for 20s
#   make restore  - put the micro-ROS firmware back

FQBN  := teensy:avr:teensy41:usb=serial2,speed=600,opt=o2std,keys=en-us
BAUD  := 115200
MCU   := TEENSY41

BUILD_DIR := $(CURDIR)/build
ACLI      := $(shell command -v arduino-cli 2>/dev/null || echo $$HOME/.local/bin/arduino-cli)
TLOADER   := $(shell command -v teensy_loader_cli 2>/dev/null || echo $$HOME/.local/bin/teensy_loader_cli)

SKETCH := $(notdir $(firstword $(wildcard $(CURDIR)/*.ino)))
HEX    := $(BUILD_DIR)/$(SKETCH).hex

PORT ?= $(shell ls /dev/serial/by-id/usb-Teensyduino_*Serial_*-if00 2>/dev/null | head -n 1)

.PHONY: compile upload watch ports restore clean

compile:
	@echo "=== Compiling for $(FQBN) ==="
	$(ACLI) compile --fqbn $(FQBN) --output-dir $(BUILD_DIR) .

# teensy_loader_cli -s cannot work here. Soft reboot is sent over HID, and
# usb=serial2 (Dual Serial, PID 048b) exposes two CDC interfaces and NO HID
# interface — so -s just prints "Error opening USB device" and waits forever.
#
# Opening the primary CDC port at 134 baud is the Teensy core's own bootloader
# trigger and needs no HID. B134 is a standard POSIX baud, so plain stty does
# it — no pyserial, which is not installed system-wide on the Jetson anyway.
#
# Also: stop micro-ros-agent.service first. It holds if02 open and blocks the
# reboot.
upload: compile
	@test -f $(HEX) || { echo "No hex at $(HEX)"; exit 1; }
	@test -n "$(PORT)" || { echo "No serial port — run 'make ports'."; exit 1; }
	@echo "=== Stopping micro-ros-agent (holds the port open) ==="
	-systemctl --user stop micro-ros-agent.service
	@echo "=== Rebooting into HalfKay via 134 baud ==="
	-stty -F $(PORT) 134
	@sleep 2
	@lsusb | grep -q 16c0:0478 || { echo "Board did not enter the bootloader"; exit 1; }
	@echo "=== Flashing $(notdir $(HEX)) ==="
	timeout 45 $(TLOADER) --mcu=$(MCU) -w -v $(HEX)
	@sleep 6
	@$(MAKE) --no-print-directory ports

watch:
	@test -n "$(PORT)" || { echo "No serial port — run 'make ports'."; exit 1; }
	@stty -F $(PORT) $(BAUD) raw -echo
	@timeout 20 cat $(PORT) || true

ports:
	@ls -l /dev/serial/by-id/ 2>/dev/null | grep -i teensy || echo "  none — board not in Serial mode"

restore:
	@echo "=== Reflashing micro-ROS firmware ==="
	$(MAKE) -C $(CURDIR)/../teensy_microros upload

clean:
	rm -rf $(BUILD_DIR)
