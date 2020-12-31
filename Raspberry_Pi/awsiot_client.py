import time
import logging
import json
import argparse
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import sys
import threading
from uuid import uuid4
from sensor_constants import *

try:
    from sensor_functions import *
except ModuleNotFoundError:
    pass    # not running this on a Pi - ok in simulation mode

# constants
cycle_period = CYCLE_PERIOD_3_S
valid_sensors = {'PPD42': PARTICLE_SENSOR_PPD42, 'SDS011': PARTICLE_SENSOR_SDS011}
TOPIC_ROOT = "$aws/rules"
RULE_NAME = "log_metriful"

# globals
log = logging.getLogger("mqtt_publisher")
simulation = False

# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
        resubscribe_results = resubscribe_future.result()
        print("Resubscribe results: {}".format(resubscribe_results))

        for topic, qos in resubscribe_results['topics']:
            if qos is None:
                sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, **kwargs):
    print("Received message from topic '{}': {}".format(topic, payload))
    global received_count
    received_count += 1
    if received_count == args.count:
        received_all_event.set()

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    log.info("Connected to broker with result code "+str(rc))

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    log.info(msg.topic+" "+str(msg.payload))

def initialise_sensor(particleSensor):
    if (simulation == False):
        # Set up the GPIO and I2C communications bus
        (GPIO, I2C_bus) = SensorHardwareSetup()

        # Apply the chosen settings to the MS430
        if (particleSensor != PARTICLE_SENSOR_OFF):
            I2C_bus.write_i2c_block_data(i2c_7bit_address, PARTICLE_SENSOR_SELECT_REG, [particleSensor])
        I2C_bus.write_i2c_block_data(i2c_7bit_address, CYCLE_TIME_PERIOD_REG, [cycle_period])

        # Enter cycle mode
        I2C_bus.write_byte(i2c_7bit_address, CYCLE_MODE_CMD)

        return I2C_bus
    else:
        return None
    

def validate_particle_sensor(candidate_sensor):
    particle_sensor = PARTICLE_SENSOR_OFF
    if (candidate_sensor == PARTICLE_SENSOR_OFF):
        log.debug("No particle sensor connected")
    else:
        if (candidate_sensor in valid_sensors):
            particle_sensor = valid_sensors[candidate_sensor]
            log.info("Using particle sensor '%s'" % candidate_sensor)
        else:
            log.error("Invalid sensor '%s' passed in - ignoring" % candidate_sensor)
            particle_sensor = PARTICLE_SENSOR_OFF
    return particle_sensor

def read_sensor(I2C_bus, particle_sensor):
    # The following quantities will be added to the payload as JSON:
    # 1 Temperature/C
    # 2 Pressure/Pa
    # 3 Humidity/%
    # 4 Air quality index
    # 5 bVOC/ppm
    # 6 SPL/dBA
    # 7 Illuminance/lux
    # 8 Particle concentration
    # 9  Air Quality Assessment summary (Good, Bad, etc.) 
    # 10 Peak sound amplitude / mPa 
    # 11 Estimated CO2 ppm

    payload = {}

    if (simulation == False):
        # Wait for the next new data release, indicated by a falling edge on READY
        while (not GPIO.event_detected(READY_pin)):
            sleep(0.05)

        # Now read all data from the MS430

        # Air data
        raw_data = I2C_bus.read_i2c_block_data(i2c_7bit_address, AIR_DATA_READ, AIR_DATA_BYTES)
        air_data = extractAirData(raw_data)
        
        # Air quality data
        # The initial self-calibration of the air quality data may take several
        # minutes to complete. During this time the accuracy parameter is zero 
        # and the data values are not valid.
        raw_data = I2C_bus.read_i2c_block_data(i2c_7bit_address, AIR_QUALITY_DATA_READ, AIR_QUALITY_DATA_BYTES)
        air_quality_data = extractAirQualityData(raw_data)
            
        # Light data
        raw_data = I2C_bus.read_i2c_block_data(i2c_7bit_address, LIGHT_DATA_READ, LIGHT_DATA_BYTES)
        light_data = extractLightData(raw_data)
        
        # Sound data
        raw_data = I2C_bus.read_i2c_block_data(i2c_7bit_address, SOUND_DATA_READ, SOUND_DATA_BYTES)
        sound_data = extractSoundData(raw_data)
            
        # Particle data
        # This requires the connection of a particulate sensor (invalid 
        # values will be obtained if this sensor is not present).
        # Also note that, due to the low pass filtering used, the 
        # particle data become valid after an initial initialization 
        # period of approximately one minute.
        raw_data = I2C_bus.read_i2c_block_data(i2c_7bit_address, PARTICLE_DATA_READ, PARTICLE_DATA_BYTES)
        particle_data = extractParticleData(raw_data, particle_sensor)
                            
        payload['temperature'] = "{:.2f}".format(air_data['T_C'])
        payload['pressure'] = "{:.2f}".format(air_data['P_Pa'])
        payload['humidity'] = "{:.2f}".format(air_data['H_pc'])
        payload['aqi'] = "{:.2f}".format(air_quality_data['AQI'])
#        payload['aqi_string'] = interpret_AQI_value(air_quality_data['AQI'])
        payload['bvoc'] = "{:.2f}".format(air_quality_data['bVOC'])
        payload['spl'] = "{:.2f}".format(sound_data['SPL_dBA'])
        payload['peak_amp'] = "{:.2f}".format(sound_data['peak_amp_mPa'])
        payload['illuminance'] = "{:.2f}".format(light_data['illum_lux'])
        payload['particulates'] = "{:.2f}".format(particle_data['concentration'])
        payload['co2e'] = "{:.2f}".format(air_quality_data['CO2e'])

    else:
        # simulated data for testing
        time.sleep(5)
        payload['temperature'] = '20'
        payload['pressure'] = '1000'
        payload['humidity'] = '50'
        payload['aqi'] = '180'
        payload['aqi_string'] = 'dummy'
        payload['bvoc'] = '500'
        payload['spl'] = '10'
        payload['peak_amp'] = '20'
        payload['illuminance'] = '500'
        payload['particulates'] = '100'
        payload['co2e'] = '50'
    
    log.debug(json.dumps(payload))
    return payload



def main(sensor_name, endpoint, cert, root_ca, key, particle_sensor, debug_flag):
    if (debug_flag):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Spin up resources
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=endpoint,
        cert_filepath=cert,
        pri_key_filepath=key,
        client_bootstrap=client_bootstrap,
        ca_filepath=root_ca,
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=sensor_name,
        clean_session=False,
        keep_alive_secs=6)

    print("Connecting to {} with client ID '{}'...".format(
        args.endpoint, args.client_id))

    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print("Connected!")

    # ensure a valid sensor type was specified (if one was)
    validated_particle_sensor = validate_particle_sensor(particle_sensor)

    # initialise & start sensor
    I2C_bus = initialise_sensor(validated_particle_sensor)
    topic_name = "{}/{}/{}".format(TOPIC_ROOT, RULE_NAME, sensor_name)
    while True:
        # read payload from sensor
        payload = read_sensor(I2C_bus, validated_particle_sensor)
        print("Publishing message to topic '{}': {}".format(topic_name, json.dumps(payload)))
        mqtt_connection.publish(
            topic=topic_name,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE)
        time.sleep(1)



if __name__ == "__main__":
    # Create the command line parser
    my_parser = argparse.ArgumentParser(description='Forward Metriful sensor values to MQTT broker') 

    # Add the arguments
    # mandatory
    my_parser.add_argument('--sensor-name', required=True, type=str, help='Name of this sensor')
    my_parser.add_argument('--endpoint', required=True, help="Your AWS IoT custom endpoint, not including a port. " +
                                                      "Ex: \"abcd123456wxyz-ats.iot.us-east-1.amazonaws.com\"")
    my_parser.add_argument('--cert', required=True, help="File path to your client certificate, in PEM format.")
    my_parser.add_argument('--key', required=True, help="File path to your private key, in PEM format.")
    my_parser.add_argument('--root-ca', required=True, help="File path to root certificate authority, in PEM format. " +
                                        "Necessary if MQTT server uses a certificate that's not already in " +
                                        "your trust store.")


    # optional
    my_parser.add_argument('--client-id', default="test-" + str(uuid4()), help="Client ID for MQTT connection.")
    my_parser.add_argument('--particle', action='store', default=PARTICLE_SENSOR_OFF, type=str, help='Optional additional particle sensor type')
    my_parser.add_argument('-d', '--debug', action='store_true', help='Debug level logging')
    my_parser.add_argument('-s', '--simulate', action='store_true', help='Simulation mode (no sensor)')

    # parse command line
    args = my_parser.parse_args()

    # set simulation mode
    simulation = args.simulate

    main(args.sensor_name, args.endpoint, args.cert, args.root_ca, args.key, args.particle, args.debug)
