"""
Basic Configuration Common Use Cases
"""
# (c) 2015-2018 Microchip Technology Inc. and its subsidiaries.
#
# Subject to your compliance with these terms, you may use Microchip software
# and any derivatives exclusively with Microchip products. It is your
# responsibility to comply with third party license terms applicable to your
# use of third party software (including open source software) that may
# accompany Microchip software.
#
# THIS SOFTWARE IS SUPPLIED BY MICROCHIP "AS IS". NO WARRANTIES, WHETHER
# EXPRESS, IMPLIED OR STATUTORY, APPLY TO THIS SOFTWARE, INCLUDING ANY IMPLIED
# WARRANTIES OF NON-INFRINGEMENT, MERCHANTABILITY, AND FITNESS FOR A
# PARTICULAR PURPOSE. IN NO EVENT WILL MICROCHIP BE LIABLE FOR ANY INDIRECT,
# SPECIAL, PUNITIVE, INCIDENTAL OR CONSEQUENTIAL LOSS, DAMAGE, COST OR EXPENSE
# OF ANY KIND WHATSOEVER RELATED TO THE SOFTWARE, HOWEVER CAUSED, EVEN IF
# MICROCHIP HAS BEEN ADVISED OF THE POSSIBILITY OR THE DAMAGES ARE
# FORESEEABLE. TO THE FULLEST EXTENT ALLOWED BY LAW, MICROCHIP'S TOTAL
# LIABILITY ON ALL CLAIMS IN ANY WAY RELATED TO THIS SOFTWARE WILL NOT EXCEED
# THE AMOUNT OF FEES, IF ANY, THAT YOU HAVE PAID DIRECTLY TO MICROCHIP FOR
# THIS SOFTWARE.

from cryptoauthlib import *
from common import *
import time
import hashlib

_atsha204_config = bytearray.fromhex(
    'C8 00 55 00 8F 8F 9F 32 8F 8F 9F 8F C0 40 C2 42'
    '00 00 AF 3F 00 00 00 00 00 00 00 00 00 00 00 00'
    '00 00 AF 8F FF 00 FF 00 FF 00 FF 00 FF 00 FF 00'
    'FF 00 FF 00 FF FF FF FF FF FF FF FF FF FF FF FF'
    'FF FF FF FF 00 00 55 55')

# Safe input if using python 2
try: input = raw_input
except NameError: pass

def configure_device():
    ATCA_SUCCESS = 0x00

    # Loading cryptoauthlib(python specific)
    load_cryptoauthlib()

    # Get the target default config
    cfg = eval('cfg_at{}a_{}_default()'.format(atca_names_map.get('sha'), atca_names_map.get('hid')))

    # Initialize the stack
    assert atcab_init(cfg) == ATCA_SUCCESS
    print('')

    # Check device type
    info = bytearray(4)
    assert atcab_info(info) == ATCA_SUCCESS
    dev_name = get_device_name(info)
    dev_type = get_device_type_id(dev_name)

    # Reinitialize if the device type doesn't match the default
    if dev_type != cfg.devtype:
        cfg.dev_type = dev_type
        assert atcab_release() == ATCA_SUCCESS
        time.sleep(1)
        assert atcab_init(cfg) == ATCA_SUCCESS

    # Request the Serial Number
    serial_number = bytearray(9)
    assert atcab_read_serial_number(serial_number) == ATCA_SUCCESS
    print('\nSerial number: ')
    print(pretty_print_hex(serial_number, indent='    '))

    # Check the zone locks
    print('Reading the Lock Status')
    is_locked = AtcaReference(False)
    assert ATCA_SUCCESS == atcab_is_locked(0, is_locked)
    config_zone_lock = bool(is_locked.value)

    assert ATCA_SUCCESS == atcab_is_locked(1, is_locked)
    data_zone_lock = bool(is_locked.value)

    print('    Config Zone: {}'.format('Locked' if config_zone_lock else 'Unlocked'))
    print('    Data Zone: {}'.format('Locked' if data_zone_lock else 'Unlocked'))

    # Get Current I2C Address
    print('\nGetting the I2C Address')
    response = bytearray(4)
    assert ATCA_SUCCESS == atcab_read_bytes_zone(0, 0, 16, response, 4)
    print('    Current Address: {:02X}'.format(response[0]))
  
    # Program the configuration zone
    print('\nProgram Configuration')
    if not config_zone_lock:
        config = _atsha204_config
        if config is not None:
            print('    Programming {} Configuration'.format(dev_name))
        else:
            print('    Unknown Device')
            raise ValueError('Unknown Device Type: {:02X}'.format(dev_type))

        # Write configuration
        assert ATCA_SUCCESS == atcab_write_bytes_zone(0, 0, 16, config, len(config))
        print('        Success')

        # Verify Config Zone
        print('    Verifying Configuration')
        config_qa = bytearray(len(config))
        atcab_read_bytes_zone(0, 0, 16, config_qa, len(config_qa))

        if config_qa != config:
            raise ValueError('Configuration read from the device does not match')
        print('        Success')

        print('    Locking Configuration')
        assert ATCA_SUCCESS == atcab_lock_config_zone()
        print('        Locked')
    else:
        print('    Locked, skipping')
        
    if not data_zone_lock:
        print('    Writing Data')
        rootkey = bytearray.fromhex (
             '33 33 33 33 33 33 33 33 33 33 33 33 33 33 33 33'
             '33 33 33 33 33 33 33 33 33 33 33 33 33 33 33 33')
        rootkey2 = bytearray.fromhex (
             '00 01 02 03 04 05 06 07 08 09 00 00 00 00 00 00'
             '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00')
        # Write rootkey to slot 2 & 3
        assert ATCA_SUCCESS == atcab_write_bytes_zone(2, 0x02, 0, rootkey, len(rootkey))
        assert ATCA_SUCCESS == atcab_write_bytes_zone(2, 0x03, 0, rootkey, len(rootkey))
        assert ATCA_SUCCESS == atcab_write_bytes_zone(2, 0x07, 0, rootkey2, len(rootkey2))
        assert ATCA_SUCCESS == atcab_write_bytes_zone(2, 0x0F, 0, rootkey2, len(rootkey2))
        
        # Get DeriveKey from RootKey + SN + SN Pad + ...
        # Must same with Client Slot0 value
        macbytes = bytearray.fromhex (
             '1C 04 01 00 EE 01 23 '
             '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'
             '00 00 00 00 00 00 00 00 00')
        snpad = bytearray.fromhex (
             '77 77 77 77 77 77 77 77 77 77 77 77 77 77 77 77'
             '77 77 77 77 77 77 77')
        sha256 = hashlib.sha256()
        sha256.update(rootkey+macbytes+serial_number+snpad)
        divKey = sha256.digest()
        print('DeriveKey: ')
        print(pretty_print_hex(divKey, indent='    '))
        # Write DeriveKey to Slot 0
        assert ATCA_SUCCESS == atcab_write_bytes_zone(2, 0, 0, divKey, len(divKey))
                
        print('    Locking Data Zone')
        assert ATCA_SUCCESS == atcab_lock_data_zone()
        print('        Locked')        
    else:
        print('    Locked, skipping')
        
    atcab_release()

if __name__ == '__main__':
    print('\nConfiguring the device with an Diversified Key configuration')
    configure_device()
    print('\nDevice Successfully Configured')
