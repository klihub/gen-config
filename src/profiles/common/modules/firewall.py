#!/usr/bin/env python3

import ipaddress
from genconfig.parser import *

class IPTables:
    BUILTIN_CHAINS = {
        'filter': [ 'INPUT', 'FORWARD', 'OUTPUT'],
        'nat':    [ 'PREROUTING', 'INPUT', 'OUTPUT', 'POSTROUTING' ],
        'mangle': [ 'PREROUTING', 'INPUT', 'FORWARD', 'OUTPUT', 'POSTROUTING' ],
        'raw':    [ 'PREROUTING', 'OUTPUT' ],
    }
    CONFIG_FILES = {
        'restore':  '/etc/sysconfig/iptables',
        'iptables': '/etc/sysconfig/iptables-commands'
    }

    class Table:
        def __init__(self, name, chains = []):
            self.name = name
            self.chains = []
            self.chain_index = {}

            for c in chains:
                if type(c) == type(''):
                    self.chains.append(IPTables.Chain(c))
                else:
                    self.chains.append(IPTables.Chain(c[0], c[1]))

            if self.name in IPTables.BUILTIN_CHAINS.keys():
                builtin = IPTables.BUILTIN_CHAINS[self.name]
                for c in builtin:
                    if c not in [x.name for x in self.chains]:
                        self.chains.append(IPTables.Chain(c))

            self.chain_index = {}
            for idx in range(0, len(self.chains)):
                self.chain_index[self.chains[idx].name] = idx

        def chain(self, name, policy = None):
            if name not in [x.name for x in self.chains]:
                c = IPTables.Chain(name, policy)
                self.chains.append(c)
                self.chain_index[name] = len(self.chains) - 1
            else:
                c = self.chains[self.chain_index[name]]
                if policy and c.policy and policy != c.policy:
                    raise RuntimeError('chain %s has conflicting policies' %
                                       (c.name, c.policy, policy))
            return c

        def write_restore(self, f):
            f.write('# %s configuration generated by %s' %
                    (self.name, __file__))
            f.write('*%s' % self.name)
            for c in self.chains:
                f.write(':%s %s [0:0]' % (c.name, c.policy))
            for c in self.chains:
                for r in c.rules:
                    f.write('%s' % r)

        def write_commands(self, f):
            f.write('# %s commands generated by %s' %
                    (self.name, __file__))
            for c in self.chains:
                if c.name not in IPTables.BUILTIN_CHAINS[self.name]:
                    f.write('iptables -t %s -N %s' % (self.name, c.name))
                if c.policy != 'ACCEPT':
                    f.write('iptables -t %s -P %s %s' %
                            (self.name, c.name, c.policy))
            for c in self.chains:
                for r in c.rules:
                    f.write('iptables -t %s -A %s %s' % (self.name, c.name, r))

    class Marker:
        def __init__(self, name):
            self.name = name

    class Chain:
        def __init__(self, name, policy = None):
            self.name = name
            self.policy = policy if policy is not None else 'ACCEPT'
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

        def insert(self, rule, after_mark = None, before_mark = None, index = 0):
            if after_mark and before_mark:
                raise RuntimeError('both before and after marker given')
            if after_mark:
                idx = self.marker_index(after_mark)
                idx += 1 + index
            elif before_mark:
                idx = self.marker_index(before_mark)
                idx -= index
            self.rules(insert, idx, rule)

        def append(self, rule, before_mark = None):
            if before_mark:
                idx = self.marker_index(before_mark)
            else:
                idx = len(self.rules)
            self.rules.insert(idx, rule)

    def __init__(self, policy = None):
        self.filter = IPTables.Table('filter',
                                     [('INPUT', policy or 'DROP'),
                                      ('FORWARD', policy or 'DROP'),
                                      'OUTPUT'])
        self.nat = IPTables.Table('nat')
        self.mangle = IPTables.Table('mangle')
        self.raw = IPTables.Table('raw')
        self.tables = {
            'filter': self.filter,
            'nat': self.nat,
            'mangle': self.mangle,
            'raw': self.raw
        }

    def set_policy(self, chain, policy):
        c = self.chains[self.chain_index[chain]]
        c.policy = policy

    def table(self, name):
        return self.tables[name]

    def chain(self, table, name):
        return self.table(table).chain(name)

    def write(self, fs, syntax = 'iptables', paths = None):
        if not paths:
            paths = IPTables.CONFIG_FILES
        f = fs.open(IPTables.CONFIG_FILES[syntax])
        if syntax == 'restore':
            for t in self.tables.values():
                t.write_restore(f)
            f.write('COMMIT')
        else:
            for t in self.tables.values():
                t.write_commands(f)
        f.close()

class Firewall(Node):
    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.node_tkn = node_tkn
        self.protected = []
        self.isolated = []
        self.trusted_interfaces = []
        self.trusted_networks = []
        self.trusted_hosts = []
        self.snats = []

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
        self.process_list(tokens, self.collect_snat, self.snats)

    def collect_snat(self, snat, snats):
        snats.append(snat.str)

    def finalize(self):
        Node.finalize(self)

    def dump(self):
        print('firewall')

def allow_conntrack(ipt):
    c = ipt.chain('filter', 'FORWARD')
    c.append('-m conntrack --cstate RELATED,ESTABLISHED -j ACCEPT')

def allow_trusted(ipt):
    c = chain = None
    for fw in Parser.nodes['firewall'].nodes:
        if fw.trusted_interfaces or fw.trusted_networks or fw.trusted_hosts:
            if not c:
                chain = 'CHECK-TRUSTED'
                c = ipt.chain('filter', chain)
            for i in fw.trusted_interfaces:
                c.append('-i %s -j ACCEPT' % i)
            for n in fw.trusted_networks:
                c.append('-s %s -j ACCEPT' % n.with_prefixlen)
            for h in fw.trusted_hosts:
                c.append('-s %s -j ACCEPT' % str(h))
    if chain:
        ipt.chain('filter', 'FORWARD').append('-j %s' % chain)
        ipt.chain('filter', 'INPUT').append('-j %s' % chain)

def allow_services(ipt):
    # accept DNS traffic if necessary
    # accept any explicitly allowed services
    pass

def isolate_interfaces(ipt):
    c = chain = None
    for fw in Parser.nodes['firewall'].nodes:
        for devices in fw.isolated:
            if not c:
                chain = 'CHECK-ISOLATE'
                c = ipt.chain('filter', chain)
            if len(devices) == 1:
                c.append('-i %s -o %s -j DROP' % (devices[0], devices[0]))
            else:
                for src in devices:
                    for dst in devices:
                        if src != dst:
                            c.append('-i %s -o %s -j DROP' % (src, dst))
    if chain:
        ipt.chain('filter', 'FORWARD').append('-j %s' % chain)

def nat_source(ipt):
    c = chain = None
    uplinks = snats = []
    for i in Parser.nodes['interface'].nodes:
        if i.uplink:
            uplinks.append(i.name)
    for fw in Parser.nodes['firewall'].nodes:
        snats += fw.snats

    snats = list(set(uplinks + snats))

    if snats:
        chain = 'SOURCE-NAT'
        c = ipt.chain('nat', chain)
        for i in Parser.nodes['interface'].nodes:
            if i.name in snats:
                if i.addresses == 'dhcp':
                    c.append('-o %s -j MASQUERADE' % i.name)
                else:
                    c.append('-o %s -j SNAT --to %s' %
                             (i.name, str(i.addresses[0])))
        ipt.chain('nat', 'POSTROUTING').append('-j %s' % chain)

def nat_destination(ipt):
    dnats = []
    pre = None
    out = None
    for fw in Parser.nodes['firewall'].nodes:
        for d in fw.children:
            if d.nodedef.name == 'dnat':
                dnats.append(d)
                if d.ifout:
                    out = d
                else:
                    pre = d

    if pre:
        pre = ipt.chain('nat', 'PREROUTING')
    if out:
        out = ipt.chain('nat', 'OUTPUT')
    for d in dnats:
        if d.ifout:
            out.append(d.generate())
        else:
            pre.append(d.generate())

def custom_rules(ipt):
    for fw in Parser.nodes['firewall'].nodes:
        for c in fw.children:
            if c.nodedef.name not in ['allow', 'block', 'deny']:
                continue
            ipt.chain('filter', c.chain).append(c.generate())

def generate_firewall(nodedef, nodes, fs):
    print('generate_firewall...')

    ipt = IPTables()

    allow_conntrack(ipt)
    allow_trusted(ipt)
    allow_services(ipt)
    isolate_interfaces(ipt)
    nat_source(ipt)
    nat_destination(ipt)
    custom_rules(ipt)

    # write out ruleset
    ipt.write(fs)


class Dnat(Node):
    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.node_tkn = node_tkn
        self.ifin = None
        self.ifout = None
        self.proto = None
        self.src_addr = self.src_port = None
        self.dst_addr = self.dst_port = None
        self.to = None

    def parse_interface(self, kw_dir, token):
        if ((kw_dir.type == '_in_' and self.ifout) or
            (kw_dir.type == '_out_' and self.ifin)):
            raise RuntimeError('%s:%s: DNAT with both in and out interfaces' %
                               self.where())
        if kw_dir.type == '_in_':
            self.ifin = token.str
        else:
            self.ifout = token.str

    def parse_protocol(self, token):
        self.proto = token.str

    def parse_srcdst(self, kw_dir, token):
        addr = port = None
        if token.type == '_int_':
            port = token.str
        else:
            spec = token.str
            if spec.startswith(':'):
                port = spec[1:]
            elif ':' in spec:
                addr, port = spec.split(':')
            else:
                addr = spec
        if kw_dir.type == '_src_':
            self.src_addr, self.src_port = addr, port
        else:
            self.dst_addr, self.dst_port = addr, port

    def parse_to(self, kw_to, token):
        self.to = token.str

    def append(self, str, option, arg):
        t = ' ' if str else ''
        if arg:
            str += '%s%s %s' % (t, option, arg)
        return str

    def restore(self, str):
        t = ' ' if self.restore else ''
        self.restore += '%s%s' % (t, str)

    def generate(self):
        str = ' '.join([x.generate() for x in self.children])
        str = self.append(str, '-i', self.ifin)
        str = self.append(str, '-o', self.ifout)
        str = self.append(str, '-p', self.proto)
        str = self.append(str, '-s', self.src_addr)
        str = self.append(str, '--sport', self.src_port)
        str = self.append(str, '-d', self.dst_addr)
        str = self.append(str, '--dport', self.dst_port)
        str = self.append(str, '-j DNAT --to-destination', self.to)
        return str

class Match(Node):
    def __init__(self, nodedef, root, parent, node_tkn, module):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.module = module
        self.args = []
        print('match %s' % self.module.str)

    def add_option(self, tkn_option, tkn_arg):
        print('match %s option %s %s' %
              (self.module.str, tkn_option.str, tkn_arg.str))
        self.args.append(tkn_option)
        self.args.append(tkn_arg)

    def generate(self):
        return '--match %s' + ' '.join([x.str for x in self.args])

class Allow(Node):
    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.node_tkn = node_tkn
        self.action = 'ACCEPT'
        self.chain = None
        self.ifin = self.ifout = None
        self.proto = None
        self.src_addr = self.src_port = self.dst_addr = self.dst_port = None

    def parse_chain(self, kw_chain):
        self.chain = kw_chain.str.strip('_').upper()

    def parse_interface(self, kw_dir, token):
        if kw_dir.type == '_in_':
            self.ifin = token.str
        else:
            self.ifout = token.str

    def parse_protocol(self, token):
        self.proto = token.str

    def parse_srcdst(self, kw_dir, token):
        addr = port = None
        if token.type == '_int_':
            port = token.str
        else:
            spec = token.str
            if spec.startswith(':'):
                port = spec[1:]
            elif ':' in spec:
                addr, port = spec.split(':')
            else:
                addr = spec
        if kw_dir.type == '_src_':
            self.src_addr, self.src_port = addr, port
        else:
            self.dst_addr, self.dst_port = addr, port

    def append(self, str, option, arg):
        t = ' ' if str else ''
        if arg:
            str += '%s%s %s' % (t, option, arg)
        return str

    def restore(self, str):
        t = ' ' if self.restore else ''
        self.restore += '%s%s' % (t, str)

    def generate(self):
        str = ' '.join([x.generate() for x in self.children])
        str = self.append(str, '-i', self.ifin)
        str = self.append(str, '-o', self.ifout)
        str = self.append(str, '-p', self.proto)
        str = self.append(str, '-s', self.src_addr)
        str = self.append(str, '--sport', self.src_port)
        str = self.append(str, '-d', self.dst_addr)
        str = self.append(str, '--dport', self.dst_port)
        str = self.append(str, '-j',  self.action)
        return str

class Block(Allow):
    def __init__(self, nodedef, root, parent, node_tkn):
        Allow.__init__(self, nodedef, root, parent, node_tkn)
        self.action = 'DROP'

class Deny(Allow):
    def __init__(self, nodedef, root, parent, node_tkn):
        Allow.__init__(self, nodedef, root, parent, node_tkn)
        self.action = 'REJECT'


NodeDef(
    'firewall', Firewall, 0,
    Lexer.Keywords(['protect', 'accept', 'drop', 'reject',
                    'trusted', 'host', 'interface', 'net', 'network',
                    'snat', 'input', 'output', 'forward',
                    'isolate']),
    Lexer.NoTokens(),
    [Parser.Rule('_protect_ _token_(, _token_)*' , 'parse_protect'),
     Parser.Rule('_isolate_ _token_(, _token_)*' , 'parse_isolate'),
     Parser.Rule('_trusted_ (_interface_|_network_|_host_) _token_',
                 'parse_trusted'),
     Parser.Rule('_trusted_ (_interface_)'       , 'parse_trusted'),
     Parser.Rule('_snat_ _token_(, _token_)*'    , 'parse_snat'   ),
     Parser.Rule('_accept_ _token_( _token_)*'   , 'parse_accept' )],
    generate_firewall
)

NodeDef('dnat', Dnat, 0,
        Lexer.Keywords(['in', 'out', 'tcp', 'udp', 'src', 'dst', 'to']),
        Lexer.NoTokens(),
        [Parser.Rule('(_in_|_out_) _token_' , 'parse_interface'),
         Parser.Rule('(_tcp_|_udp_)'        , 'parse_protocol' ),
         Parser.Rule('(_src_|_dst_) _token_', 'parse_srcdst'   ),
         Parser.Rule('_to_ _token_'         , 'parse_to'       )])

NodeDef('match', Match, 1,
        Lexer.NoKeywords(),
        [Lexer.TokenRegex(r'(-.*)', 'option')],
        [Parser.Rule('_option_ _token_', 'add_option')])

NodeDef('allow', Allow, 0,
        Lexer.Keywords(['input', 'forward', 'output', 'in', 'out',
                        'src', 'dst', 'tcp', 'udp', 'icmp']),
        Lexer.NoTokens(),
        [Parser.Rule('(_input_|_output_|_forward_)' , 'parse_chain'    ),
         Parser.Rule('(_in_|_out_) _token_'         , 'parse_interface'),
         Parser.Rule('(_tcp_|_udp_|_icmp_)'         , 'parse_protocol' ),
         Parser.Rule('(_src_|_dst_) (_token_|_int_)', 'parse_srcdst'   )])

NodeDef('block', Block, 0,
        Lexer.Keywords(['input', 'forward', 'output', 'in', 'out',
                        'src', 'dst', 'tcp', 'udp', 'icmp']),
        Lexer.NoTokens(),
        [Parser.Rule('(_input_|_output_|_forward_)' , 'parse_chain'    ),
         Parser.Rule('(_in_|_out_) _token_'         , 'parse_interface'),
         Parser.Rule('(_tcp_|_udp_|_icmp_)'         , 'parse_protocol' ),
         Parser.Rule('(_src_|_dst_) (_token_|_int_)', 'parse_srcdst'   )])

NodeDef('deny', Deny, 0,
        Lexer.Keywords(['input', 'forward', 'output', 'in', 'out',
                        'src', 'dst', 'tcp', 'udp', 'icmp']),
        Lexer.NoTokens(),
        [Parser.Rule('(_input_|_output_|_forward_)' , 'parse_chain'    ),
         Parser.Rule('(_in_|_out_) _token_'         , 'parse_interface'),
         Parser.Rule('(_tcp_|_udp_|_icmp_)'         , 'parse_protocol' ),
         Parser.Rule('(_src_|_dst_) (_token_|_int_)', 'parse_srcdst'   )])
