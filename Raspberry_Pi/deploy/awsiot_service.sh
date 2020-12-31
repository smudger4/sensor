#!/bin/sh
# usage: aws_service.sh


DATE=`date '+%Y-%m-%d %H:%M:%S'`
echo "AWS IoT service started at ${DATE}" | systemd-cat -p info
cd /home/pi/code/github/sensor/Raspberry_Pi

/usr/bin/python3 awsiot_client.py --endpoint a2pu44lklh9jkw-ats.iot.eu-west-1.amazonaws.com --root-ca /certs/root-CA.crt --cert /certs/bugsby-shed.cert.pem --key /certs/bugsby-shed.private.key --sensor-name shed --debug  | /usr/bin/logger
