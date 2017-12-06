#!/usr/bin/env python3

import ipaddress

from genconfig.parser import *

class DhcpServer(Node):

    V4_TYPE = type(ipaddress.ip_address('0.0.0.0'))

    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.link = None
        self.net = None
        self.domain = None
        self.range = None
        self.router = None
        self.nameservers = []
        self.max_lease = 0
        self.default_lease = 0

    def parse_net(self, kwnet, address):
        self.net = ipaddress.ip_interface(address.str).network

    def parse_domain(self, kwnet, domain):
        self.domain = domain.str

    def parse_range(self, kwrange, *tokens):
        if tokens[0].type == '_intrange_':
            beg, end = tokens[0].str.split('-')
            self.range = (int(beg), int(end))
        elif tokens[0].type == '_address_':
            self.range = (ipaddress.ip_address(tokens[0].str),
                          ipaddress.ip_address(tokens[2].str))

    def parse_router(self, kw_router, router):
        self.router = router.str

    def parse_dns(self, kw_nameservers, *tokens):
        self.process_list(tokens, self.process_dns)

    def process_dns(self, addr):
        self.nameservers.append(addr.str)

    def parse_lease(self, kwlease, time):
        if kwlease.str == 'max-lease':
            self.max_lease = int(time.str)
        else:
            self.default_lease = int(time.str)

    def check_net(self):
        if self.parent.nodedef.name == 'interface':
            nets = [x.network for x in self.parent.addresses]
            if self.net and self.net not in nets:
                raise RuntimeError((
                    '%s:%d: DHCP server net not configured for parent ' +
                    'interface %s') % (self.where() + (self.parent.name, )))
        else:
            nets = []

        if not self.net:
            if not nets:
                raise RuntimeError((
                    '%s:%d: DHCP server without a net should be nested ' +
                    'under an interface') % self.where())
            self.net = nets[0]

    def check_link(self):
        if self.parent.nodedef.name == 'interface':
            self.link = self.parent.name
        else:
            for i in Parser.nodes['interface'].nodes:
                if type(i.addresses) != type([]):
                    continue
                for a in i.addresses:
                    if a in self.net:
                        self.link = i.name
                        break
                if self.link:
                    break
            if not self.link:
                raise RuntimeError('No link for DHCP server %s' % s.net)

    def check_range(self):
        if not self.range:
            num_hosts = self.net.num_addresses
            min = (int)(num_hosts / 8 + 1)
            max = (int)(num_hosts / 2 - 2)
            self.range = (min, max)

        if type(self.range[0]) == type(0):
            self.range = (self.net[self.range[0]], self.net[self.range[1]])

    def check_router(self):
        if not self.router:
            if self.parent.nodedef.name == 'interface':
                for r in self.parent.addresses:
                    if r in self.net:
                        self.router = r
                        break
        else:
            if type(self.router) == type(''):
                if self.router.isdigit():
                    self.router = self.net[int(self.router)]
                elif self.router in ['first', 'last']:
                    max = self.net.num_addresses - 2
                    self.router = self.net[1 if self.router == 'first' else max]
                else:
                    raise RuntimeError('%s:%d: invalid router' % self.where())
            elif type(self.router) == self.V4_TYPE:
                if self.router not in self.net:
                    raise RuntimeError('%s:%d: router not part of net' %
                                       self.where())

    def check_dns(self):
        if not self.nameservers:
            self.nameservers = [self.router]
        else:
            nsl = []
            for ns in self.nameservers:
                if type(ns) == type(''):
                    if ns == 'router':
                        nsl.append(self.router)
                    elif ns.isdigit():
                        nsl.append(self.net[int(ns)])
                    else:
                        raise RuntimeError('%s:%d: invalid nameserver %s' %
                                           (self.where() + (ns,)))
                elif type(ns) == self.V4_TYPE:
                    nsl.append(ns)
                else:
                    raise RuntimeError('%s:%d: invalid nameserver %s' %
                                       str(ns))
            self.nameservers = nsl

    def check_lease(self):
        if not self.max_lease and not self.default_lease:
            self.default_lease = 4 * 60 * 60
        if not self.max_lease and self.default_lease:
            self.max_lease = self.default_lease
        elif not self.default_lease and self.max_lease:
            self.default_lease = self.max_lease
        if self.max_lease < self.default_lease:
            self.max_lease = self.default_lease

    def finalize(self):
        self.check_net()
        self.check_link()
        self.check_range()
        self.check_router()
        self.check_dns()
        self.check_lease()
        Node.finalize(self)

    def dump(self):
        print('DHCP server:')
        print('    network: %s' % self.net)
        print('    link: %s' % self.link)
        print('    range: %s - %s' % (self.range[0], self.range[1]))
        print('    router: %s' % self.router)
        print('    nameservers: %s' %
              ','.join([str(x) for x in self.nameservers]))
        print('    lease: default %d, max %d' %
              (self.default_lease, self.max_lease))


    def generate(self, fs):
        log.progress('generating DHCP server for link %s...' % self.link)
        net, mask = self.net.with_netmask.split('/')
        f = fs.open('/etc/dhcpd.conf')
        f.write('subnet %s netamask %s {' % (net, mask))
        if self.domain:
            f.write('  option domain-name "%s";' % self.domain)
        f.write('  option doman-name-servers %s;' %
                ','.join([str(x) for x in self.nameservers]))
        f.write('  option routers %s;' % self.router)
        f.write('  range %s %s;' % (self.range[0], self.range[1]))
        f.write('  default-lease-time %s;' % self.default_lease)
        f.write('  max-lease-time %s;' % self.max_lease)
        f.write('}')
        f.close()

def generate_dhcp_servers(nodedef, servers, fs):
    links = []
    for s in servers:
        s.generate(fs)
        links.append(s.link)
    f = fs.open('/etc/sysconfig/dhcpd')
    f.write('INTERFACES="%s"' % ' '.join(links))
    f.close()


NodeDef(
    'dhcp-server', DhcpServer, 0,
    Lexer.Keywords(['net', 'domain', 'range', 'router', 'nameservers',
    'max-lease', 'default-lease']),
    [Lexer.TokenRegex(r'([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?', 'address')],
    [Parser.Rule('_net_ _address_'                    , 'parse_net'   ),
     Parser.Rule('_domain_ _token_'                   , 'parse_domain'),
     Parser.Rule('_range_ _intrange_'                 , 'parse_range' ),
     Parser.Rule('_range_ _address_ - _address_'      , 'parse_range' ),
     Parser.Rule('_router_ _int_'                     , 'parse_router'),
     Parser.Rule('_router_ _address_'                 , 'parse_router'),
     Parser.Rule('_router_ _token_'                   , 'parse_router'),
     Parser.Rule('_nameservers_ (_int_|_address_|_router_)(, (_int_|_address_|_router_))*', 'parse_dns'),
     Parser.Rule('(_max-lease_|_default-lease_) _int_', 'parse_lease' )],
    generate_dhcp_servers
)
