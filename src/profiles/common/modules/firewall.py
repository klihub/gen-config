#!/usr/bin/env python3

import ipaddress
from genconfig.parser import *

class IPTables:
    class Table:
        def __init__(self, name, chains = []):
            self.name = name
            self.chains = chains
            self.index = {}
            for idx in range(0, len(self.chains)):
                self.index[self.chains[idx].name] = idx

        def chain(self, name):
            return self.chains[self.index[name]]

        def add_chain(self, name, policy = None):
            if name in keys(self.chains):
                return self.chains[self.index[name]]
            else:
                self.chains.name = chain = Chain(name, policy)
                self.index[chain.name] = len(self.chains)
                return chain

    class Marker:
        def __init__(self, name):
            self.name = name

    class Chain:
        def __init__(self, name, policy = None):
            self.name = name
            self.policy = policy
            self.rules = []

        def marker(self, name, index = -1):
            if index > -1:
                self.rules.insert(index, Marker(name))
            else:
                self.rules.append(Marker(name))
        
        def marker_index(self, name):
            for idx in range(0, len(self.rules)):
                if type(self.rules[idx]) == Marker:
                    return idx
            return -1

    class Match:
        def __init__(self, name, options):
            self.name = name
            self.options = options

    class Rule:
        def __init__(self, selectors, target, target_opts = None, matches = []):
            self.selectors = selectors
            self.matches = matches
            self.target = target
            self.target_options = target_opts
            
    def __init__(self, policy = None):
        self.filter = IPTables.Table('filter', [
            IPTables.Chain('INPUT', policy),
            IPTables.Chain('FORWARD', policy),
            IPTables.Chain('OUTPUT')])
        self.nat = IPTables.Table('nat', [
            IPTables.Chain('PREROUTING'),
            IPTables.Chain('INPUT'),
            IPTables.Chain('OUTPUT'),
            IPTables.Chain('POSTROUTING')])
        self.mangle = IPTables.Table('mangle', [
            IPTables.Chain('PREROUTING'),
            IPTables.Chain('INPUT'),
            IPTables.Chain('FORWARD'),
            IPTables.Chain('OUTPUT'),
            IPTables.Chain('POSTROUTING')])
        self.raw = IPTables.Table('raw', [
            IPTables.Chain('PREROUTING'),
            IPTables.Chain('OUTPUT')])
        self.tables = {
            'filter': self.filter,
            'nat': self.nat,
            'mangle': self.mangle,
            'raw': self.raw
        }

    def table(self, name):
        return self.tables[name]

    def chain(self, tname, cname):
        return table(tname).chain(cname)

    def marker_index(self, tname, cname, mname):
        return table(tname).chain(cname).marker_index(mname)

    def insert(self, tbl_chain, *rule_args, after_marker = None):
        tbl, chain = tbl_chain.split(':')
        if after_marker:
            idx = self.marker_index(tbl, chain, after_) + 1
        else:
            idx = 0
        chain.rules.insert(idx, IPTables.Rule(rule_args))
        
    def append(self, tbl_chain, *rule_args, before_marker = None):
        tbl, chain = tbl_chain.split(':')
        if before_marker:
            idx = self.marker_index(tbl, chain, before_marker = None)
        else:
            idx = len(chain.rules)
        chain.rules.insert(idx, IPTables.Rule(rule_args))
        


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
    ipt = IPTables()
#    ipt.insert('filter:FORWARD', '', '', 'ACCEPT'
               matches = [('conntrack', '--ctstate RELATED,ESTABLISHED')])
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

