"""
Basic Dirive Key Verify Common Use Cases
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

# Safe input if using python 2
try: input = raw_input
except NameError: pass


def authentication_counter(iface='hid', device='ecc', i2c_addr=None, keygen=True, **kwargs):
    ATCA_SUCCESS = 0x00

    # Loading cryptoauthlib(python specific)
    load_cryptoauthlib()

    # Get the target default config
    cfg = eval('cfg_at{}a_{}_default()'.format(atca_names_map.get(device), atca_names_map.get(iface)))

    # Set interface parameters
    if kwargs is not None:
        for k, v in kwargs.items():
            icfg = getattr(cfg.cfg, 'atca{}'.format(iface))
            setattr(icfg, k, int(v, 16))

    # Basic Raspberry Pi I2C check
    if 'i2c' == iface and check_if_rpi():
        cfg.cfg.atcai2c.bus = 1

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
    print('Serial number: ')
    print(pretty_print_hex(serial_number, indent='    '))
    
    # Check the device locks
    print('Check Device Locks')
    is_locked = AtcaReference(False)
    assert atcab_is_locked(0, is_locked) == ATCA_SUCCESS
    config_zone_locked = bool(is_locked.value)
    print('    Config Zone is %s' % ('locked' if config_zone_locked else 'unlocked'))
    
    assert atcab_is_locked(1, is_locked) == ATCA_SUCCESS
    data_zone_locked = bool(is_locked.value)
    print('    Data Zone is %s' % ('locked' if data_zone_locked else 'unlocked'))
    
    # Run a nonce command to get a random data
    nonce_in = bytearray.fromhex(
          '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'
          '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00')
    nonce_out = bytearray(32)
    assert atcab_nonce_rand(nonce_in, nonce_out) == ATCA_SUCCESS
    print('Nonce: ')
    print(pretty_print_hex(nonce_out, indent='    '))
    
    # Run a MAC command at Slot0, Slot0 have programmed with DeriveKey from RootKey
    digest = bytearray(32)
    assert atcab_mac(0x00, 0x00, nonce_out, digest) == ATCA_SUCCESS
    print('Digest: ')
    print(pretty_print_hex(digest, indent='    '))
    
    # Get DeriveKey from RootKey + SN + SN Pad + ...
    # Must same with Client Slot0 value
    rootkey = bytearray.fromhex(
          '33 33 33 33 33 33 33 33 33 33 33 33 33 33 33 33'
          '33 33 33 33 33 33 33 33 33 33 33 33 33 33 33 33')
    
    # 01 23 50 16 CE FE 0B 8D EE
    opcode = bytearray.fromhex(
          '08 00 00 00'
          '00 00 00 00 00 00 00 00 00 00 00'
          'EE 00 00 00 00 01 23 00 00')
    optbytes = rootkey+nonce_out+opcode
    sha256 = hashlib.sha256() #Must init hashlib again here
    sha256.update(optbytes)
    mac = sha256.digest()
    print('MAC: ')
    print(pretty_print_hex(mac, indent='    '))
    
    if mac == digest:
       print('Authentication Success!\n')
    else:
       print('Authentication Fail!\n')
    
    atcab_release()

if __name__ == '__main__':
    parser = setup_example_runner(__file__)
    parser.add_argument('--i2c', help='I2C Address (in hex)')
    parser.add_argument('--gen', default=True, help='Generate new keys')
    args = parser.parse_args()

    if args.i2c is not None:
        args.i2c = int(args.i2c, 16)

    print('\nDirive Key Verify Starting...')
    authentication_counter(args.iface, args.device, args.i2c, args.gen, **parse_interface_params(args.params))
    #print('Authentication Counter Test Success')
