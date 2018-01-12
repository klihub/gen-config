#!/usr/bin/env python3

from genconfig.parser import *


class Nameserver(Node):
    def __init__(self, nodedef, root, parent, node_tkn, backend):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.backend = backend.str

def generate_dnsmasq(ns, fs):
    print('* should generate dnsmasq config...')

def generate_bind(ns, fs):
    raise RuntimeError('support for bind is not implemented')

def generate_nameserver(nodedef, nodes, fs):
    if len(nodes) > 1:
        raise RuntimeError('more than one nameserver definitions')
    ns = nodes[0]
    if ns.backend not in Nameserver.backends.keys():
        raise RuntimeError('unknown nameserver %s selected' % ns.backend)
    Nameserver.backends[ns.backend](ns, fs)

Nameserver.backends = {
    'dnsmasq': generate_dnsmasq,
    'bind'   : generate_bind
}

NodeDef('nameserver', Nameserver, 1, [], [], [], generate_nameserver)
