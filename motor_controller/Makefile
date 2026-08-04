# Arduino Nano Motor Controller Makefile
# Usage:
#   make         - compile
#   make upload  - compile & upload
#   make monitor - read serial output for 5 seconds
#   make mon     - continuous serial monitor (Ctrl+C to exit)
#   make all     - compile, upload, and monitor
#   make clean   - remove build artifacts

FQBN := arduino:avr:nano
BAUD := 9600

# Auto-detect USB serial port: prefer usbserial (Nano/CH340) over usbmodem
PORT := $(shell ls /dev/cu.usbserial* 2>/dev/null | head -n 1)
ifeq ($(PORT),)
  PORT := $(shell ls /dev/cu.usbmodem* 2>/dev/null | head -n 1)
endif

BUILD_DIR := build

.PHONY: all compile upload monitor mon clean info

all: upload monitor

compile:
	@echo "=== Compiling for $(FQBN) ==="
	arduino-cli compile --fqbn $(FQBN) --output-dir $(BUILD_DIR) .

upload: compile
ifndef PORT
	$(error No Arduino serial port found. Plug in the Nano or set PORT=/dev/...)
endif
	@echo "=== Uploading to $(PORT) ==="
	arduino-cli upload -p $(PORT) --fqbn $(FQBN) --input-dir $(BUILD_DIR) .

monitor:
ifndef PORT
	$(error No Arduino serial port found. Set PORT=/dev/...)
endif
	@echo "=== Reading serial output from $(PORT) at $(BAUD) baud ==="
	@python3 monitor.py $(PORT) -b $(BAUD) -d 5

mon:
ifndef PORT
	$(error No Arduino serial port found. Set PORT=/dev/...)
endif
	@echo "=== Continuous serial monitor on $(PORT) at $(BAUD) baud ==="
	@echo "(press Ctrl+C to exit)"
	@python3 monitor.py $(PORT) -b $(BAUD)

clean:
	@echo "=== Cleaning build artifacts ==="
	rm -rf $(BUILD_DIR)

info:
	@echo "FQBN : $(FQBN)"
	@echo "PORT : $(PORT)"
	@echo "BAUD : $(BAUD)"
