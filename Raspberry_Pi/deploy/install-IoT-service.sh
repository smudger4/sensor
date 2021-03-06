#!/bin/bash
# install systemd service - run as root (sudo)
SERVICE=sensor_logging_service

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: install-service.sh <API KEY> [<PARTICLE SENSOR TYPE>] - exiting"
    exit 1
fi

if [ "$#" -eq 1 ]; then
    # only API key provided
    # insert api-key from command line into service file
    sed "s/xxxxx/$1/g" template-IoT.service > /tmp/$SERVICE.tmp
    sed "s/yyyyy//g" /tmp/$SERVICE.tmp > $SERVICE.service
else
    # API key & sensor type provided
    sed "s/xxxxx/$1/g" template.service > /tmp/$SERVICE.tmp
    sed "s/yyyyy/Environment=\"PARTICLE_SENSOR_TYPE=$2\"/g" /tmp/$SERVICE.tmp > $SERVICE.service
fi
rm /tmp/$SERVICE.tmp

cp $SERVICE.sh /usr/bin/
chmod +x /usr/bin/$SERVICE.sh
cp $SERVICE.service /etc/systemd/system/
chmod 644 /etc/systemd/system/$SERVICE.service

systemctl enable $SERVICE
systemctl start $SERVICE
systemctl status $SERVICE