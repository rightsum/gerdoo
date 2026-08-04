I'm building a robot and need to step down a 3S Li-ion battery (10.8V nominal, 12.6V full, 9V empty) to 5V for these loads on a single rail:

- RPLIDAR C1: 230mA continuous, 800mA startup surge
- 2× SG90 9G servos (pan/tilt gimbal): ~200mA idle each, ~700mA stall each, sudden current spikes when moving
- COB LED strip: ~300mA

Total: ~1.1A continuous, ~2.5A peak during servo stalls

The Teensy 4.1 microcontroller is powered separately from the Jetson's USB port (5V, 100mA), so it's NOT on this rail.

I have one AZDelivery LM2596S buck converter with a built-in 3-digit voltmeter. Specs:
- Output: 3.3-24V adjustable (I'd set it to 5V)
- Input: 4V minimum
- 2A continuous, 3A with additional cooling
- ~75% efficiency

I'm considering this vs a Mini560 (MP2315, ~93% efficiency, 3A, much smaller). However, I've personally experienced the Mini560 shutting down completely (latching off) when motors/servos create current spikes on a shared ground, requiring a manual power cycle to restart. This is a documented issue: https://www.reddit.com/r/arduino/comments/1d8paqe/watch_out_for_these_mini560_inrush_current_shuts/

Questions:
1. Is the LM2596S suitable for this load (LIDAR + 2 servos + LED)?
2. Will it survive servo stall current spikes without shutting down?
3. Is the 2A continuous rating sufficient with adequate margin?
4. Any concerns about the LIDAR's 800mA startup surge combined with servo spikes?
5. Should I add any decoupling/bulk capacitors, and if so what values?