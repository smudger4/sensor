#!/bin/bash
# install systemd service - run as root (sudo)

SERVICE=sensor_logging_service

# insert api-key from command line into service file
sed 's/xxxxx/$1/g' template.service > $SERVICE.service

cp $SERVICE.sh /usr/bin/
chmod +x /usr/bin/$SERVICE.sh
cp $SERVICE.service /etc/systemd/system/
chmod 644 /etc/systemd/system/$SERVICE.service

systemctl start $SERVICE
systemctl enable $SERVICE
systemctl status $SERVICE