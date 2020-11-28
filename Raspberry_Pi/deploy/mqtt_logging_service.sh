#!/bin/sh
# usage: mqtt_logging_service.sh <SENSOR NAME> <BROKER ADDR> [<PARTICLE SENSOR>]

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: mqtt_logging_service.sh <SENSOR NAME> <BROKER ADDR> [<PARTICLE
SENSOR>] - exiting"
    exit 1
fi

DATE=`date '+%Y-%m-%d %H:%M:%S'`
echo "MQTT logging service started at ${DATE}" | systemd-cat -p info
cd /home/pi/code/github/sensor/Raspberry_Pi

if [ "$#" -eq 2 ]; then
    /usr/bin/python3 mqtt_client.py $1 $2 | /usr/bin/logger
else
    /usr/bin/python3 mqtt_client.py $1 $2 --particle $3 | /usr/bin/logger
fi
