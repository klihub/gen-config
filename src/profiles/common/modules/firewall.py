#!/usr/bin/env python3

from genconfig.parser import *

class Firewall(Node):
    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.node_tkn = node_tkn
        self.isolations = []

    def parse_accept(self, kw_accept, *tokens):
        pass

    def parse_snat(self, kw_snat, *tokens):
        pass

    def parse_isolate(self, kw_isolate, *tokens):
        link_list = []
        self.process_list(tokens, self.collect_link, link_list)
        self.isolations.append(link_list)

    def collect_link(self, link, link_list):
        link_list.append(link.str)

    def finalize(self):
        Node.finalize(self)

    def dump(self):
        print('firewall')

def generate_firewall(nodedef, nodes, fs):
    print('generate_firewall...')

NodeDef(
    'firewall', Firewall, 0,
    Lexer.Keywords(['accept', 'drop', 'reject',
                    'snat', 'dnat', 'on',
                    'input', 'output', 'forward',
                    'isolate']),
    Lexer.NoTokens(),
    [Parser.Rule('_accept_ _token_( _token_)*'  , 'parse_accept' ),
     Parser.Rule('_snat_ _on_ _token_( _token_)*'    , 'parse_snat'   ),
     Parser.Rule('_isolate_ _token_(, _token_)*', 'parse_isolate')],
    generate_firewall
)
