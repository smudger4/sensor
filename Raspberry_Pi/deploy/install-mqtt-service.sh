#!/bin/bash
# install systemd service - run as root (sudo)
SERVICE=mqtt_logging_service

if [ "$#" -ne 2 ]; then
    echo "Usage: install-service.sh <SENSOR NAME> <BROKER IP> - exiting"
    exit 1
fi

# sensor name & sensor type provided
sed "s/xxxxx/$1/g" template.service > /tmp/$SERVICE.tmp
sed "s/yyyyy/$2/g" /tmp/$SERVICE.tmp > $SERVICE.service

rm /tmp/$SERVICE.tmp

cp $SERVICE.sh /usr/bin/
chmod +x /usr/bin/$SERVICE.sh
cp $SERVICE.service /etc/systemd/system/
chmod 644 /etc/systemd/system/$SERVICE.service

systemctl enable $SERVICE
systemctl start $SERVICE
systemctl status $SERVICE