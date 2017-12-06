#!/usr/bin/env python3

from genconfig.parser import *

class Hardware(Node):
    def __init__(self, nodedef, root, parent, node_tkn):
        Node.__init__(self, nodedef, root, parent, node_tkn)
        self.ethernet = { 'setup': None, 'devices': [] }

    def parse_ethernet(self, ethernet, setup_method, *tokens):
        self.ethernet['setup'] = setup_method.str
        self.process_list(tokens, self.process_ethernet)

    def process_ethernet(self, dev_tkn):
        if '=' in dev_tkn.str:
            name, mac = dev_tkn.str.split('=')
            dev = (name, mac)
        else:
            dev = dev_tkn.str
        self.ethernet['devices'].append(dev)

    def finalize(self):
        pass

    def dump(self):
        print('Ethernet devices:')
        for dev in self.ethernet['devices']:
            if type(dev) == type(()):
                print('  %s = %s' % (dev))
            else:
                print('  %s' % dev)

    def generate_ethernet(self, fs):
        log.progress('generating ethernet HW configuration...')
        t = ''
        interfaces = ''
        for dev in self.ethernet['devices']:
            if type(dev) == type(()):
                name, mac = dev
                interfaces += '%s%s=%s' % (t, name, mac)
            else:
                interfaces += '%s%s' % (t, dev)
            t=','
        f = fs.open('/etc/sysconfig/ethernet')
        f.write('INTERFACES="%s"' % interfaces)
        f.write('SETUP_METHOD="%s"' % self.ethernet['setup'])
        f.close()

    def generate(self, fs):
        self.generate_ethernet(fs)

def generate_hardware(nodedef, nodes, fs):
    for hw in nodes:
        hw.generate(fs)

NodeDef(
    'hardware', Hardware, 0,
    Lexer.Keywords(['ethernet', 'sort-mac']),
    [Lexer.TokenRegex('[0-9a-fA-F](:[0-9a-fA-F]){6}', 'mac')],
    [Parser.Rule('_ethernet_ _sort-mac_ _token_(, _token_)*', 'parse_ethernet')],
    generate_hardware
)





#
#
#

class CfgModule:
    def __init__(self, name, type, extra, keywords, tokens, rules, generate):
        self.name = name
        self.type = type
        self.extra_args = extra
        self.generate = generate
        self.keywords = []
        self.tokens = []
        self.rules = []
        for kw in keywords:
            self.keywords.append(Lexer.TokenKeyword(kw))
        for t in tokens:
            for c in t:
                if c in '[]()*?+{}':
                    self.tokens.append(Lexer.TokenRegex(t[0], t[1]))
                    break
            else:
                self.tokens.append(Lexer.TokenStr(t[0], t[1]))
        self.rules = []
        for r in rules:
            self.rules.append(Parser.Rule(r[0], r[1]))

CfgModule(
    'hardware', Hardware, 0,
    ['ethernet', 'by-mac'],
    [('[0-9a-fA-F](:[0-9a-fA-F]){5}', 'macaddr')],
    [('_ethernet_ _by-mac_ _token_(, _token_)*', 'parse_ethernet')],
    generate_hardware
)
