#!/usr/bin/env python
# NiteLite - a python daemon process started at system boot, and stopped on shutdown
#          - the default LED pattern is twinkling but if motion is detected, one of 4
#            different patterns are chosen and these are used for 10s after motion detection
#
# Please see our GitHub repository for more information: https://github.com/PiStuffing/NiteLite
#
# Once running you'll need to press ctrl-C to cancel stop the script or run
# sudo /etc/init.d/nitelited.sh stop

from __future__ import division
import signal
import time
from smbus import SMBus
import RPi.GPIO as GPIO
import random
import math

# command register addresses for the SN3218 IC used in PiGlow
CMD_ENABLE_OUTPUT = 0x00
CMD_ENABLE_LEDS = 0x13
CMD_SET_PWM_VALUES = 0x01
CMD_UPDATE = 0x16

class PiGlow:
	i2c_addr = 0x54 # fixed i2c address of SN3218 ic
	bus = None

	def __init__(self, i2c_bus=1):
		self.bus = SMBus(i2c_bus)

		# first we tell the SN3218 to enable output (turn on)
		self.write_i2c(CMD_ENABLE_OUTPUT, 0x01)

		# then we ask it to enable each bank of LEDs (0-5, 6-11, and 12-17)
		self.write_i2c(CMD_ENABLE_LEDS, [0xFF, 0xFF, 0xFF])

	def update_leds(self, values):
		self.write_i2c(CMD_SET_PWM_VALUES, values)
		self.write_i2c(CMD_UPDATE, 0xFF)

	def write_i2c(self, reg_addr, value):
		# if a single value is provided then wrap it in a list so we can treat
		if not isinstance(value, list):
			value = [value];

		# write the data to the SN3218
		self.bus.write_i2c_block_data(self.i2c_addr, reg_addr, value)


LED_ARM_TOP = 0
LED_ARM_LEFT = 1
LED_ARM_RIGHT = 2

LED_COLOUR_RED = 0
LED_COLOUR_ORANGE = 1
LED_COLOUR_YELLOW = 2
LED_COLOUR_GREEN = 3
LED_COLOUR_BLUE = 4
LED_COLOUR_WHITE = 5

LED_PATTERN_TWINKLE = 0
LED_PATTERN_GLOW = 1
LED_PATTERN_SWELL = 2
LED_PATTERN_DROPLET = 3
LED_PATTERN_SNAKE = 4


#------------------------------------------------------------
# Set up the LED spiral arm / colour mappings
#------------------------------------------------------------
led_map = []
for arm in range(0,3):
	led_map.append([])
	for colour in range(0,6):
		led_map[arm].append(0)

led_map[LED_ARM_TOP][LED_COLOUR_RED] = 6
led_map[LED_ARM_TOP][LED_COLOUR_ORANGE] = 7
led_map[LED_ARM_TOP][LED_COLOUR_YELLOW] = 8
led_map[LED_ARM_TOP][LED_COLOUR_GREEN] = 5
led_map[LED_ARM_TOP][LED_COLOUR_BLUE] = 4
led_map[LED_ARM_TOP][LED_COLOUR_WHITE] = 9
led_map[LED_ARM_LEFT][LED_COLOUR_RED] = 0
led_map[LED_ARM_LEFT][LED_COLOUR_ORANGE] = 1
led_map[LED_ARM_LEFT][LED_COLOUR_YELLOW] = 2
led_map[LED_ARM_LEFT][LED_COLOUR_GREEN] = 3
led_map[LED_ARM_LEFT][LED_COLOUR_BLUE] = 14
led_map[LED_ARM_LEFT][LED_COLOUR_WHITE] = 12
led_map[LED_ARM_RIGHT][LED_COLOUR_RED] = 17
led_map[LED_ARM_RIGHT][LED_COLOUR_ORANGE] = 16
led_map[LED_ARM_RIGHT][LED_COLOUR_YELLOW] = 15
led_map[LED_ARM_RIGHT][LED_COLOUR_GREEN] = 13
led_map[LED_ARM_RIGHT][LED_COLOUR_BLUE] = 11
led_map[LED_ARM_RIGHT][LED_COLOUR_WHITE] = 10

#------------------------------------------------------------
# Set up the LED number array
#------------------------------------------------------------
leds = []
for led in range(0, 18):
	leds.append(0)

#------------------------------------------------------------
# Set up the LED brightness array
#------------------------------------------------------------
levels = [0, 1, 2, 4, 8, 16, 32, 64, 128]

#------------------------------------------------------------
# Set up the shutdown handler
#------------------------------------------------------------
def ShutdownHandler(signal, frame):
	global keep_looping
	keep_looping = False

#------------------------------------------------------------
# Set up the PIR movement detection callback
#------------------------------------------------------------
def PIRCallback(channel):
	global motion_detected_time
	global led_pattern
	global leds

	if led_pattern == LED_PATTERN_TWINKLE:
		led_pattern = random.randint(1, 4)
	motion_detected_time = time.time()

#------------------------------------------------------------
# Set up the PIR movement detection
#------------------------------------------------------------
GPIO_PIR = 18
GPIO.setmode(GPIO.BOARD)
GPIO.setup(GPIO_PIR, GPIO.IN, GPIO.PUD_DOWN)
GPIO.add_event_detect(GPIO_PIR, GPIO.RISING, PIRCallback, 0)

#------------------------------------------------------------
# Final steps of setup
#------------------------------------------------------------
signal.signal(signal.SIGINT, ShutdownHandler)
piglow = PiGlow(1)
keep_looping = True
motion_detected_time = time.time() - 5.1

while keep_looping:

#------------------------------------------------------------
# Drop back to the default LED pattern?
#------------------------------------------------------------
	if time.time() - motion_detected_time >= 5.0:
		led_pattern = LED_PATTERN_TWINKLE
		twinkle_count = 0

#------------------------------------------------------------
# TWINKLE: 0: Random LED lit with random, decaying brightness
#------------------------------------------------------------
	if led_pattern == LED_PATTERN_TWINKLE:

		# dim all lit LEDs by one step in the levels list
		# first find the index into the brightness list
		# This relies on the fact that values in the levels
		# list are all 2^n
		for led in range(0, 18):
			mant, level = math.frexp(leds[led])
			if mant == 0.0:
				level = 0
			if level > 0:
				leds[led] = levels[level - 1]


		# Add a random LED every 10 cycles with random brightness
		if twinkle_count == 0:
			leds[random.randint(0, 17)] = levels[random.randint(0, 8)]
		twinkle_count = (twinkle_count + 1) % 10

		piglow.update_leds(leds)
		time.sleep(0.1)

#------------------------------------------------------------
# GLOW: 1; All LEDs glow at a low level
#------------------------------------------------------------
	elif led_pattern == LED_PATTERN_GLOW:
		for led in range(0, 18):
			leds[led] = levels[4]
		piglow.update_leds(leds)

#------------------------------------------------------------
# SWELL: 2; All LEDs brightness swelling up and down
#------------------------------------------------------------
	elif led_pattern == LED_PATTERN_SWELL:
		for level in range(0, 8):
			for led in range(0, 18):
				leds[led] = levels[level]
			piglow.update_leds(leds)
			time.sleep(0.1)

		for level in range(8, 0, -1):
			for led in range(0, 18):
				leds[led] = levels[level]
			piglow.update_leds(leds)
			time.sleep(0.1)

#------------------------------------------------------------
# DROPLET 3; Same colour sweeping up and down all the arms together at fixed brightness
#------------------------------------------------------------
	elif led_pattern == LED_PATTERN_DROPLET:

		for colour in range(0, 5):
			for arm in range(0, 3):
				leds[led_map[arm][colour]] = 0x80	

			piglow.update_leds(leds)
			for arm in range(0,3):
				leds[led_map[arm][colour]] = 0x00

			time.sleep(0.1)
		for colour in range(5, 0, -1):
			for arm in range(0,3):
				leds[led_map[arm][colour]] = 0x80

			piglow.update_leds(leds)
			for arm in range(0,3):
				leds[led_map[arm][colour]] = 0x00

			time.sleep(0.1)

#------------------------------------------------------------
# SNAKE: 4; Light each arm sequentially, with LED brightness brighter at center
#------------------------------------------------------------
	elif led_pattern == LED_PATTERN_SNAKE:
		for arm in range(0, 3):
			for colour in range (0, 5):
				leds[led_map[arm][colour]] = levels[colour + 1]
			piglow.update_leds(leds)
			time.sleep(0.1)


			for colour in range (5, 0, -1):
				leds[led_map[arm][colour]] = levels[colour + 1]

			piglow.update_leds(leds)
			time.sleep(0.1)
			for colour in range(0, 6):
				leds[led_map[arm][colour]] = 0x00


# set all the LEDs to "off" when Ctrl+C is pressed before exiting
for led in range(0, 18):
	leds[led] = 0x0
piglow.update_leds(leds)

