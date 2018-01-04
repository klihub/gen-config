#!/usr/bin/env python3

import ipaddress
from genconfig.parser import *

class Firewall(Node):
    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.node_tkn = node_tkn
        self.protected = []
        self.isolated = []
        self.trusted_interfaces = []
        self.trusted_networks = []
        self.trusted_hosts = []
        self.rules = []

    def parse_protect(self, kw_protect, *tokens):
        self.process_list(tokens, self.collect_device, self.protected)

    def parse_isolate(self, kw_isolate, *tokens):
        devices = []
        self.process_list(tokens, self.collect_device, devices)
        self.isolated.append(devices)

    def collect_device(self, device, devices):
        devices.append(device.str)

    def parse_trusted(self, kw_trusted, kw_kind, *token):
        if kw_kind.str == 'host':
            self.trusted_hosts.append(ipaddress.ip_address(token[0].str))
        elif kw_kind.str == 'network' or kw_kind.str == 'net':
            self.trusted_networks.append(ipaddress.ip_interface(token[0].str))
        else:
            if not token:
                if self.parent.nodedef.name != 'interface':
                    raise RuntimeError('implicit trusted interface must be ' +
                                       'nested under an interface')
                else:
                    name = self.parent.name
            else:
                name = token[0].str
            self.trusted_interfaces.append(name)

    def parse_accept(self, kw_accept, *tokens):
        pass

    def parse_snat(self, kw_snat, *tokens):
        pass


    def finalize(self):
        Node.finalize(self)

    def dump(self):
        print('firewall')

def generate_firewall(nodedef, nodes, fs):
    print('generate_firewall...')
    fw = nodes[0]
    for devices in fw.isolated:
        if len(devices) > 1:
            for src in devices:
                for dst in devices:
                    print('iptables -t filter -I FORWARD -i %s -o %s -j DROP' %
                          (src, dst))
        else:
            src = dst = devices[0]
            print('iptables -t filter -I FORWARD -i %s -o %s -j DROP' %
                  (src, dst))


NodeDef(
    'firewall', Firewall, 0,
    Lexer.Keywords(['protect', 'accept', 'drop', 'reject',
                    'trusted', 'host', 'interface', 'net', 'network',
                    'snat', 'dnat', 'input', 'output', 'forward',
                    'isolate']),
    Lexer.NoTokens(),
    [Parser.Rule('_protect_ _token_(, _token_)*' , 'parse_protect'),
     Parser.Rule('_isolate_ _token_(, _token_)*' , 'parse_isolate'),
     Parser.Rule('_trusted_ (_interface_|_network_|_host_) _token_',
                 'parse_trusted'),
     Parser.Rule('_trusted_ (_interface_)', 'parse_trusted'),

     Parser.Rule('_accept_ _token_( _token_)*'   , 'parse_accept' ),
     Parser.Rule('_snat_ _token_( _token_)*', 'parse_snat'   )],
    generate_firewall
)

