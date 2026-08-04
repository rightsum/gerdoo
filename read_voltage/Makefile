# Arduino Nano Voltage Reader Makefile
# Usage:
#   make         - compile the sketch
#   make upload  - compile and upload to the Nano
#   make monitor - open serial monitor (read for 5 sec)
#   make all     - compile, upload, and show output
#   make clean   - remove build artifacts

# FQBN for Arduino Nano (ATmega328P)
FQBN := arduino:avr:nano

# Serial baud rate
BAUD := 9600

# Auto-detect USB serial port, or override: make PORT=/dev/cu.usbserial-xxx
# Prioritize usbserial (Arduino Nano/CH340) over usbmodem (other boards)
PORT := $(shell ls /dev/cu.usbserial* 2>/dev/null | head -n 1)
ifeq ($(PORT),)
  PORT := $(shell ls /dev/cu.usbmodem* 2>/dev/null | head -n 1)
endif

# Build directory
BUILD_DIR := $$(pwd)/build

.PHONY: all compile upload monitor clean

all: upload monitor

compile:
	@echo "=== Compiling for $(FQBN) ==="
	arduino-cli compile --fqbn $(FQBN) --output-dir $(BUILD_DIR) .

upload: compile
ifndef PORT
	$(error No Arduino serial port found. Plug in the board or set PORT=...)
endif
	@echo "=== Uploading to $(PORT) ==="
	arduino-cli upload -p $(PORT) --fqbn $(FQBN) --input-dir $(BUILD_DIR) .

monitor:
ifndef PORT
	$(error No Arduino serial port found. Set PORT=...)
endif
	@echo "=== Reading serial output from $(PORT) at $(BAUD) baud ==="
	@python3 monitor.py $(PORT) -b $(BAUD) -d 5

# Continuous monitor (keeps reading until Ctrl+C)
mon:
ifndef PORT
	$(error No Arduino serial port found. Set PORT=...)
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
