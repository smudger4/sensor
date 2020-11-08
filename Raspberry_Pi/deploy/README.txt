Metriful sensors

Set IoT_cloud_logging.py to run as a service, by installing the sensor_logging_service.sh as a service using systemctl. Unit file is sensor_logging_service.service
Mandatory arg is the API key

sudo ./install-service.sh <API-KEY>

Instructions as per https://www.linode.com/docs/quick-answers/linux/start-service-at-boot/,
but in summary:

Setup:
sudo cp sensor_logging_service.sh /usr/bin/
sudo chmod +x /usr/bin/sensor_logging_service.sh
sudo cp sensor_logging_service.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/sensor_logging_service.service

Start & test:
sudo systemctl start sensor_logging_service
sudo systemctl status sensor_logging_service

Enable for boot:
sudo systemctl enable sensor_logging_service
