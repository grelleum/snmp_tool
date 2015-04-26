snmp_tool
=======
snmp_tool is intended for copying Cisco router and switch configuration files to and from network based servers via snmp.  This is especially useful when making configuration changes to access methods like tacacs.  If a change to authentication has locked you out of the CLI, you can revert the change via pushing the configuration via snmp.

snmp_tool is designed to be compatible with both Python 2.6, 2.7, and 3.x.<br>
snmp_tool requires pysnmp module installed.<br>

Implements the features of the Cisco config copy MIB:  ftp://ftp.cisco.com/pub/mibs/v2/CISCO-CONFIG-COPY-MIB.my <br>
Based on information found within the Cisco document: "How To Copy Configurations To and From Cisco Devices Using SNMP"
http://www.cisco.com/c/en/us/support/docs/ip/simple-network-management-protocol-snmp/15217-copy-configs-snmp.html

##### Usage: #####
Instantiate the snmp_tool class with a hostname or ip address and optionally a community string and udp port number can be provided.  These default to 'private' and 161, respectively.<br>
Output from the pysnmp package has been simplified in that the data is returned without the error status.  Instead error with raise and OSError exception and will attempt to provide as much decoded error information as is available.

The snmp_tool class provides get, set, and copy methods.  get and set are standard snmp operations and can be used with any SNMPv1 or SNMPv2c device.  copy is specific to compatible Cisco routers and switches and the main purpose of the  module.

Once you have instantiated the object, you can use it to perform the copy.<br>
object.copy(source=None, destination=None, server=None, filename=None, username=None, password=None)<br>
source and destination are always required and can be one of these: ['running', 'startup', 'tftp', 'ftp', 'rcp', 'scp', 'sftp']<br>
server and filename are required when copying to/from a server.<br>
With the exception of tftp, username and password are also required when copying to/from a server.<br>

##### Example: #####
```
from snmp_tool import snmp_tool
snmp = snmp_tool('172.17.0.32', 'private')
try:
    # Fetch configuration changes from tftp server.
    snmp.copy('tftp', 'running', '172.17.0.254', 'change_12345')
    # Save the running configuration to nvram.
    snmp.copy('running', 'startup')
    # Backup running configuration to secrue server
    snmp.copy(source='running', destination='scp',
        server='172.17.0.254', filename='NYCWAN01', 
        username='router', password='secret')
except OSError as exception:
    print(exception)
```
<br>
Intersting find: importing unicode_literals from __future__ in python2 breaks compatibility with the pysnmp package.  Apparently the authors of pysnmp detect the python version running and require a Python 2 bytestring when runnning in Python 2.
