#!/bin/bash
# install systemd service - run as root (sudo)
SERVICE=mqtt_logging_service

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: install-mqtt-service.sh <SENSOR NAME> <BROKER ADDR> [<PARTICLE SENSOR>] - exiting"
    exit 1
fi

if [ "$#" -eq 2 ]; then
    # sensor name & sensor type provided
    sed "s/xxxxx/$1/g" template-mqtt.service > /tmp/$SERVICE-1.tmp
    sed "s/yyyyy/$2/g" /tmp/$SERVICE-1.tmp > /tmp/$SERVICE-2.tmp
    sed "s/zzzzz//g" /tmp/$SERVICE-2.tmp > $SERVICE.service
else
    # sensor name, sensor type & particle sensor provided
    sed "s/xxxxx/$1/g" template-mqtt.service > /tmp/$SERVICE-1.tmp
    sed "s/yyyyy/$2/g" /tmp/$SERVICE-1.tmp > /tmp/$SERVICE-2.tmp
    sed "s/zzzzz/$3/g" /tmp/$SERVICE-2.tmp > $SERVICE.service
fi

rm /tmp/$SERVICE-*.tmp

cp $SERVICE.sh /usr/bin/
chmod +x /usr/bin/$SERVICE.sh
cp $SERVICE.service /etc/systemd/system/
chmod 644 /etc/systemd/system/$SERVICE.service

systemctl enable $SERVICE
systemctl start $SERVICE
systemctl status $SERVICE