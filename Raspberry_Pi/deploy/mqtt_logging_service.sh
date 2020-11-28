#!/bin/sh

DATE=`date '+%Y-%m-%d %H:%M:%S'`
echo "MQTT logging service started at ${DATE}" | systemd-cat -p info
cd /home/pi/code/github/sensor/Raspberry_Pi
/usr/bin/python3 mqtt_client.py $1 $2 | /usr/bin/logger
