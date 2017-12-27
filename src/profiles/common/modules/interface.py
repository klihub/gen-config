#!/usr/bin/env python3

import ipaddress

from genconfig.parser import *
from genconfig.lexer import *

class Interface(Node):
    def __init__(self, nodedef, root, parent, node_tkn, name):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.name = name.str
        self.vlans = []
        self.addresses = []

    def parse_config(self, kw_config, state, *tokens):
        if state.str == 'down':
            self.addresses = 'down'
        elif state.str == 'dhcp':
            self.addresses = 'dhcp'
        elif state.str == 'ipv4':
            self.process_list(tokens, self.process_address)

    def process_address(self, addr):
        self.addresses.append(ipaddress.ip_interface(addr.str))

    def parse_vlans(self, kw_vlans, *tokens):
        self.process_list(tokens, self.process_vlan)

    def process_vlan(self, vlan):
        if vlan.type == '_int_':
            id = int(vlan.str)
            if id not in self.vlans:
                self.vlans.append(id)
        else:
            beg, end = map(lambda x: int(x), vlan.str.split('-'))
            diff = +1 if end > beg else -1
            for id in range(beg, end, diff):
                if id not in self.vlans:
                    self.vlans.append(id)
        self.vlans.sort()

    def check_config(self):
        if not self.addresses:
            raise RuntimeError('%s:%d: interface %s has no configuration' %
                               (self.where() + (self.name,)))

    def check_vlans(self):
        if '.' in self.name and self.vlans:
            raise RuntimeError('%s:%d: interface %s has nested VLANs' %
                               (self.where() + (self.name,)))

    def finalize(self):
        self.check_config()
        self.check_vlans()
        Node.finalize(self)

    def dump(self):
        print('interface %s:' % self.name)
        if type(self.addresses) == type(''):
            print('    address: %s' % self.addresses)
        else:
            print('    addresses: %s' %
                  ','.join([x.with_prefixlen for x in self.addresses]))
        print('    vlans: %s' % ','.join([str(x) for x in self.vlans]))
        Node.dump(self)


    def generate(self, fs):
        log.progress('generating network interface %s...' % self.name)
        prio = 20 if '.' in self.name else 10
        path = '/etc/systemd/network/%d-%s.network' % (prio, self.name)
        f = fs.open(path, ini=True)
        f.write('Name=%s' % self.name, 'Match')
        if type(self.addresses) == type(''):
            if self.addresses == 'dhcp':
                f.write('DHCP=ipv4', 'Network')
        else:
            for a in self.addresses:
                f.write('Address=%s' % str(a), 'Network')
        f.write('LinkLocalAddressing=no', 'Network')
        for id in self.vlans:
            f.write('VLAN=%s.%d' % (self.name, id), 'Network')
        f.close()
        for id in self.vlans:
            log.progress('generating device for VLAN #%d...' % id)
            f = fs.open('/etc/systemd/network/00-%s-vlan%d.netdev' %
                        (self.name, id), ini=True)
            f.write('Name=%s.%d' % (self.name, id), 'NetDev')
            f.write('Kind=vlan')
            f.write('Id=%d' % id, 'VLAN')
            f.close()

def generate_interfaces(nodedef, interfaces, fs):
    for i in interfaces:
        i.generate(fs)

NodeDef(
    'interface', Interface, 1,
    Lexer.Keywords(['vlans', 'config', 'ipv4', 'down', 'dhcp']),
    [Lexer.TokenRegex(r'([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?', 'address')],
    [Parser.Rule('_vlans_ (_int_|_intrange_)(, (_int_|_intrange_))*', 'parse_vlans' ),
     Parser.Rule('_config_ _down_'                            , 'parse_config'),
     Parser.Rule('_config_ _dhcp_'                            , 'parse_config'),
     Parser.Rule('_config_ _ipv4_ _address_(, _address_)*'    , 'parse_config')],
    generate_interfaces,
)
