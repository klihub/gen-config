#!/usr/bin/env python3

import re, configparser
from genconfig.parser import *

class IANAServices:
    ALIASEN = {
        'dhcp':         'bootps',
        'dhcpd':        'bootps',
        'dhcp-server':  'bootps',
        'dhcp-client':  'bootpc',
        'secure-shell': 'ssh',
        'openssh':      'ssh',
        'sshd':         'ssh',
    }
    def __init__(self, path = '/etc/services'):
        self.services = { 'tcp': {}, 'udp': {} }
        with open(path) as f:
            for line in f:
                line = line.split('#')[0].strip()
                if not line:
                    continue
                line = re.sub('[ \t]+', ' ', line)
                service, port_proto, *aliasen = line.split(' ')
                port, proto = port_proto.split('/')
                if proto not in self.services.keys():
                    self.services[proto] = {}
                self.services[proto][service] = port
                for a in aliasen:
                    self.services[proto][a] = port

    def port(self, name, proto = 'tcp'):
        if name in self.services[proto].keys():
            return self.services[proto][name]
        if name in self.ALIASEN.keys():
            return self.port(self.ALIASEN[name], proto)

    def protocol(self, name):
        return 'tcp' # XXX TODO

class SystemdService:
    def __init__(self, name):
        self.name = name
        self.path = '/usr/lib/systemd/system/' + name + '.service'
        self.file = configparser.ConfigParser(strict = False)
        self.file.read_file(open(self.path), self.path)

    def get(self, section, key, default = None):
        return self.file.get(section, key) or default

class Service(Node):
    services = IANAServices()

    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.enable = []
        self.disable = []

    def parse_service(self, state, service, *tokens):
        name = service.str
        if tokens:
            proto = tokens[0].str
        else:
            proto = self.services.protocol(name)
        port = self.services.port(name, proto)

        if state.str == 'enable':
            self.enable.append((name, proto))
        else:
            self.disable.append((name, proto))


def generate_services(nodedef, nodes, fs):
    enabled = []
    disabled = []
    for s in Parser.nodes['service'].nodes:
        enabled += [e[0] for e in s.enable]
        disabled += [e[0] for e in s.disable]
    enabled = list(set(enabled))
    disabled = list(set(disabled))

    for s in enabled:
        service = SystemdService(s)
        target = service.get('Install', 'WantedBy', 'multi-user.target')
        src = service.path
        dst = '/etc/systemd/system/%s/%s.service' % (target, s)
        fs.symlink(src, dst)

    for s in disabled:
        src = '/dev/null'
        dst = '/etc/systemd/system/%s.service' % s
        fs.symlink(src, dst)

NodeDef('service', Service, 0,
        Lexer.Keywords(['enable', 'disable', 'tcp', 'udp']),
        Lexer.NoTokens(),
        [Parser.Rule('(_enable_|_disable_) _token_( _tcp_|_udp_)?',
                     'parse_service')],
        generate_services)


