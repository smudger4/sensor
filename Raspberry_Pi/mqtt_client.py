import time
import logging
import json
import argparse
import paho.mqtt.client as mqtt
from sensor_constants import *

try:
    from sensor_functions import *
except ModuleNotFoundError:
    pass    # not running this on a Pi - ok in simulation mode

# constants
cycle_period = CYCLE_PERIOD_100_S
valid_sensors = {'PPD42': PARTICLE_SENSOR_PPD42, 'SDS011': PARTICLE_SENSOR_SDS011}

# globals
log = logging.getLogger("mqtt_publisher")
simulation = False

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
                            
        payload['temperature'] = "{:.1f}".format(air_data['T_C'])
        payload['pressure'] = air_data['P_Pa']
        payload['humidity'] = "{:.1f}".format(air_data['H_pc'])
        payload['aqi'] = "{:.1f}".format(air_quality_data['AQI'])
        payload['aqi_string'] = interpret_AQI_value(air_quality_data['AQI'])
        payload['bvoc'] = "{:.2f}".format(air_quality_data['bVOC'])
        payload['spl'] = "{:.1f}".format(sound_data['SPL_dBA'])
        payload['peak_amp'] = "{:.2f}".format(sound_data['peak_amp_mPa'])
        payload['illuminance'] = "{:.2f}".format(light_data['illum_lux'])
        payload['particulates'] = "{:.2f}".format(particle_data['concentration'])
        payload['co2e'] = "{:.1f}".format(air_quality_data['CO2e'])

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


def main(sensor_name, broker_ip, particle_sensor, debug_flag):
    if (debug_flag):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    client = mqtt.Client()
    client.enable_logger(logger=log)
    client.on_connect = on_connect

    # connect to the broker
    client.connect(broker_ip, 1883, 60)
    client.loop_start()

    # ensure a valid sensor type was specified (if one was)
    validated_particle_sensor = validate_particle_sensor(particle_sensor)

    # initialise & start sensor
    I2C_bus = initialise_sensor(validated_particle_sensor)

    while True:
        # read payload from sensor
        payload = read_sensor(I2C_bus, validated_particle_sensor)
        client.publish("metriful/%s" % sensor_name, json.dumps(payload))


if __name__ == "__main__":
    # Create the command line parser
    my_parser = argparse.ArgumentParser(description='Forward Metriful sensor values to MQTT broker') 

    # Add the arguments
    # mandatory
    my_parser.add_argument('sensor_name', metavar='sensor_name', type=str, help='Name of this sensor')
    my_parser.add_argument('broker_ip', metavar='broker_ip', type=str, help='IP address of the MQTT broker')

    # optional
    my_parser.add_argument('--particle', action='store', default=PARTICLE_SENSOR_OFF, type=str, help='Optional additional particle sensor type')
    my_parser.add_argument('-d', '--debug', action='store_true', help='Debug level logging')
    my_parser.add_argument('-s', '--simulate', action='store_true', help='Simulation mode (no sensor)')

    # parse command line
    args = my_parser.parse_args()

    # set simulation mode
    simulation = args.simulate

    main(args.sensor_name, args. broker_ip, args.particle, args.debug)
