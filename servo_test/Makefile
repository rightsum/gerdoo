FQBN := arduino:avr:nano
BAUD := 9600

PORT := $(shell ls /dev/cu.usbserial* 2>/dev/null | head -n 1)
ifeq ($(PORT),)
  PORT := $(shell ls /dev/cu.usbmodem* 2>/dev/null | head -n 1)
endif

BUILD_DIR := build

.PHONY: all compile upload monitor clean info

all: upload monitor

compile:
	@echo "=== Compiling servo test ==="
	arduino-cli compile --fqbn $(FQBN) --output-dir $(BUILD_DIR) .

upload: compile
ifndef PORT
	$(error No Arduino serial port found. Set PORT=/dev/...)
endif
	@echo "=== Uploading to $(PORT) ==="
	arduino-cli upload -p $(PORT) --fqbn $(FQBN) --input-dir $(BUILD_DIR) .

monitor:
ifndef PORT
	$(error No Arduino serial port found. Set PORT=/dev/...)
endif
	@echo "=== Monitoring $(PORT) ==="
	@python3 monitor.py $(PORT) -b $(BAUD)

clean:
	rm -rf $(BUILD_DIR)

info:
	@echo "PORT : $(PORT)"
	@echo "BAUD : $(BAUD)"
