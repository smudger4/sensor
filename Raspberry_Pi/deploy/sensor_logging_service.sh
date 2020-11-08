#!/bin/sh

DATE=`date '+%Y-%m-%d %H:%M:%S'`
echo "Sensor logging service started at ${DATE}" | systemd-cat -p info
cd /home/pi/code/github/sensor/Raspberry_Pi
/usr/bin/python3 IoT_cloud_logging.py | /usr/bin/logger
