"""
snmp_config_copy.py

Provides functions to automate configuration backup and retreival
via snmp set operations.

Implements the features of the Cisco config copy MIB:
ftp://ftp.cisco.com/pub/mibs/v2/CISCO-CONFIG-COPY-MIB.my

Based on information found within the Cisco document:
"How To Copy Configurations To and From Cisco Devices Using SNMP"
http://www.cisco.com/c/en/us/support/docs/ip/simple-network-management-protocol-snmp/15217-copy-configs-snmp.html

Requires pysnmp module installed.

TODO: Add testing.
TODO: Allow server to be specified as a name - must lookup ip address.
TODO: Add snmp_walk() as an iterable.
TODO: Add SNMPv3 support.
TODO: Add IPv6 support in copy MIB and detect version in copy function.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
#from __future__ import unicode_literals  # actually breaks py2 snmp library!

import time
import random

from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1902  # provides snmp data types
""" rfc1902 data types:
    ApplicationSyntax
    Bits
    Counter32
    Counter64
    Gauge32
    Integer
    Integer32
    IpAddress
    ObjectName
    ObjectSyntax
    OctetString
    Opaque
    SimpleSyntax
    TimeTicks
    Unsigned32
"""


class snmp_tool(object):
    """Provides snmp get and set methods, 
    and a method for copying Cisco configuration files.
    
    Instantiate object with a hostname/ip address
    Optionally a community string, udp port number and source address of snmp server can be provided.
    These default to 'private' and 161, respectively.
    """

    def __init__(self, host, community='private', port=161,  src_address='0.0.0.0'):
        self.host = host
        self.community = community
        self.port = port
        self.system_description = '1.3.6.1.2.1.1.1.0'
        self.system_name = '1.3.6.1.2.1.1.5.0'
        self.src_address = src_address

    def _raise_exception_on_error(self, results):
        errorIndication, errorStatus, errorIndex, varBinds = results
        if errorIndication:
            raise OSError(errorIndication)
        if errorStatus:
            error_message = 'SNMP error %s at %s' % (
                errorStatus.prettyPrint(), 
                errorIndex and varBinds[int(errorIndex)-1] or '?'
                )
            raise OSError(error_message)

    def get(self, *args):
        """Implements the snmp get function. Returns a list."""
        snmp_obj = cmdgen.CommandGenerator()
        results = snmp_obj.getCmd(
            cmdgen.CommunityData(self.community),
            cmdgen.UdpTransportTarget((self.host, self.port)).setLocalAddress((self.src_address, 0)),
            *args
            )
        self._raise_exception_on_error(results)
        return results[3]

    def set(self, *args):
        """Implements the snmp set function. Returns a list."""
        snmp_obj = cmdgen.CommandGenerator()
        results = snmp_obj.setCmd(
            cmdgen.CommunityData(self.community),
            cmdgen.UdpTransportTarget((self.host, self.port)).setLocalAddress((self.src_address, 0)),
            *args
            )
        self._raise_exception_on_error(results)
        return results[3]

    def _create_sets(self):
        self.local_set = set(['running', 'startup'])
        self.network_set = set(['tftp', 'ftp', 'rcp', 'scp', 'sftp'])
        self.auth_required = self.network_set.difference(['tftp'])
        self.valid_set = self.local_set.union(self.network_set)

    def _delete_table_entry(self, mib):
        results = self.set(mib.action('destroy'))

    def _wait_for_copy_then_delete_row(self, mib):
        """Common function for use by the copy functions.
        Waits for copy to complete and deletes the row when completed.
        """
        result = ''
        for x in range(1, 300):
            time.sleep(0.1)
            result = mib.status(self.get(mib.status()))
            if result in ['not available', 'successful']:
                break
            elif result == 'failed':
                result = mib.cause_of_failure(self.get(mib.cause_of_failure()))
                break
        self._delete_table_entry(mib)
        return 'snmp copy result: ' + result

    def copy(self, source=None, destination=None, server=None, filename=None, 
            username=None, password=None, protocol=None):
        mib = CiscoCopyMib()
        self.mibby = mib
        self._create_sets()
        self._delete_table_entry(mib)
        parameters = []
        for location in (source, destination):
            if location not in self.valid_set:
                raise ValueError('Must provide valid source and destination.')
            if location in self.network_set:
                if server is None or filename is None:
                    raise ValueError('Missing server and/or filename.')
                parameters.append(mib.server_address(server))
                parameters.append(mib.filename(filename))
            if location in self.auth_required:
                if username is None or password is None:
                    raise ValueError('Missing username and/or password.')
                parameters.append(mib.username(username))
                parameters.append(mib.password(password))
        if source in self.network_set:
            source, protocol = 'network_file', source
        elif destination in self.network_set:
            destination, protocol = 'network_file', destination
        parameters.append(mib.source(source))
        parameters.append(mib.destination(destination))
        if protocol in self.network_set:
            parameters.append(mib.protocol(protocol))
        parameters.append(mib.action('create_and_go'))
        self.set(*parameters)
        return(self._wait_for_copy_then_delete_row(mib))


class CiscoCopyMib(object):
    """Python object implementation of the Cisco Config Copy MIB
    ftp://ftp.cisco.com/pub/mibs/v2/CISCO-CONFIG-COPY-MIB.my
    
    The included methods return an oid when no argument is given,
    or a tulple that includes and oid and an rfc1902 typed value.
    """

    def __init__(self):
        self.row = str(random.randint(100, 999))
        self.base_oid = '.1.3.6.1.4.1.9.9.96.1.1.1.1.'
        self.copy_status = [
            'not available',
            'waiting',
            'running',
            'successful',
            'failed',
            ]
        self.failure_causes = [
            'copy completed successfully',
            'cause unknown',
            'bad filename or authentication failure',
            'operation timed out',
            'no memory',
            'no config',
            'unsupported protocol',
            'some config apply failed',
            'system not ready',
            'request aborted',
            ]

    def action(self, arg=None):
        """Takes action on the snmp table row."""
        oid = self.base_oid + '14.' + self.row
        if arg is None:
            return oid
        else:
            options = [
                'active', 
                'not_in_service', 
                'not_ready', 
                'create_and_go', 
                'create_and_wait', 
                'destroy',
                ]
            index = options.index(arg) + 1
            value = rfc1902.Integer(index)
            #return (oid.encode, value)
            return (oid, value)

    def protocol(self, arg=None):
        """Protocol to use to transfer file.  
        
        Not required when source and destination are the localhost.
        These are the valid options:
        tftp:  Transfer File Transfer Protocol 
        ftp:   File Transfer protocol  # NOT SUPPORTED ???
        rcp:   Remote Copy Protocol
        scp:   Secure Copy Protocol
        sftp:  Secure File Transfer Protocol
        """
        oid = self.base_oid + '2.' + self.row
        if arg is None:
            return oid
        else:
            options = ['tftp', 'ftp', 'rcp', 'scp', 'sftp']
            index = options.index(arg) + 1
            value = rfc1902.Integer(index)
            return (oid, value)

    def source(self, arg=None):
        """Copy source."""
        oid = self.base_oid + '3.' + self.row
        if arg is None:
            return oid
        else:
            options = [
                'network_file', 
                'ios_file', 
                'startup', 
                'running', 
                'terminal',
                ]
            index = options.index(arg) + 1
            value = rfc1902.Integer(index)
            return (oid, value)

    def destination(self, arg=None):
        """Copy destination."""
        oid = self.base_oid + '4.' + self.row
        if arg is None:
            return oid
        else:
            options = [
                'network_file', 
                'ios_file', 
                'startup', 
                'running', 
                'terminal',
                ]
            index = options.index(arg) + 1
            value = rfc1902.Integer(index)
            return (oid, value)

    def server_address(self, arg=None):
        """Set server IP address when copying to/from a remote server.
        
        This object can just hold only IPv4 Transport
        type, it is deprecated and replaced by 
        ccCopyServerAddressRev1." 
        """
        oid = self.base_oid + '5.' + self.row
        if arg is None:
            return oid
        else:
            value = rfc1902.IpAddress(arg)
            return (oid, value)

    def filename(self, arg=None):
        """Set filename when copying to/from a remote server."""
        oid = self.base_oid + '6.' + self.row
        if arg is None:
            return oid
        else:
            value = rfc1902.OctetString(arg)
            return (oid, value)

    def username(self, arg=None):
        """Set the username when server requires it."""
        oid = self.base_oid + '7.' + self.row
        if arg is None:
            return oid
        else:
            value = rfc1902.OctetString(arg)
            return (oid, value)

    def password(self, arg=None):
        """Set the password when server requires it."""
        oid = self.base_oid + '8.' + self.row
        if arg is None:
            return oid
        else:
            value = rfc1902.OctetString(arg)
            return (oid, value)

    def status(self, results=None):
        """Returns an oid for retrieving the copy status
        or a string if a status is provided.
        """
        if results is None:
            return self.base_oid + '10.' + self.row
        elif results[0][1]:
            index = int(rfc1902.Integer(results[0][1]))
            return self.copy_status[index]

    def start_time(self):
        return self.base_oid + '11.' + self.row

    def completion_time(self):
        return self.base_oid + '12.' + self.row

    def cause_of_failure(self, results=None):
        """Cause of the copy failure.

        Returns an oid for retrieving the cause of a failue.
        Optional argument is the return list from an snmp get.
        Returns a string based on failure code in the return list.
        Returns False if returned value is 'NoSuchInstance'.
        """
        if results is None:
            return self.base_oid + '13.' + self.row
        elif results[0][1]:
            index = int(rfc1902.Integer(results[0][1]))
            return self.failure_causes[index]
        else:
            return False

    def server_address_type(self, arg=None):
        """Set server IP address type to IPv4 or IPv6.
            Not Implemented - need to find 'InetAddressType'
        """
        oid = self.base_oid + '15.' + self.row
        if arg is None:
            return oid
        else:
            #value = rfc1902.InetAddressType(arg)
            value = rfc1902.IpAddress(arg)
            return (oid, value)

    def server_address_rev1(self, arg=None):
        """Set server IP address when copying to/from a remote server."""
        oid = self.base_oid + '16.' + self.row
        if arg is None:
            return oid
        else:
            value = rfc1902.IpAddress(arg)
            return (oid, value)

