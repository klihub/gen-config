#!/usr/bin/env python3

import os, re
from genconfig.lexer import *
import genconfig.log as log

class Node:
    def __init__(self, nodedef, root, parent, node_tkn):
        self.root = root
        self.nodedef = nodedef
        self.node_tkn = node_tkn
        self.parent = parent
        self.children = []
        self.nodedef.nodes.append(self)
        if parent:
            parent.children.append(self)

    def process_list(self, list_tokens, cb, *cb_args):
        for i in range(0, len(list_tokens), 2):
            cb(list_tokens[i], *cb_args)

    def where(self, tkn = None):
        if not tkn:
            tkn = self.node_tkn
        return (tkn.file, tkn.line)

    def finalize(self):
        for c in self.children:
            c.finalize()

    def dump(self):
        for c in self.children:
            c.dump()

    def generate(self, fs, nodes, is_first):
        if is_first:
            print('should generate configuration for node %s' % str(self))

class NodeDef:
    def __init__(self, name, type, extra, keywords, tokens, rules,
                 generate = None):
        self.name = name
        self.type = type
        self.extra_tokens = extra
        self.keywords = keywords
        self.tokens = tokens
        self.rules = rules
        self.generate = generate
        self.nodes = []
        Lexer.keywords[name] = keywords
        Lexer.tokens[name] = tokens
        Parser.rules[name] = rules
        Parser.nodes[name] = self

    def generate_config(self, fs):
        if self.generate:
            self.generate(self, self.nodes, fs)

class RuleSet(Lexer):
    """A class for handling the rules the parser understands."""
    rules = {}
    nodes = {}

    def __init__(self, profile, path):
        Lexer.__init__(self, profile, path)

    def compile(self, rule):
        log.debug('compiling rule %s => %s' % (rule.pattern, rule.callback))
        pattern = ''
        i = 0
        while i < len(rule.pattern):
            c = rule.pattern[i]
            if c != '_':
                pattern += c
                i += 1
                continue

            beg = i
            end = i + 1
            for j in range(beg + 1, len(rule.pattern)):
                if rule.pattern[j] in ['_', ' ']:
                    end = j
                    break
            if end == beg or rule.pattern[end] != '_':
                raise RuntimeError('unterminated token in %s' % rule.pattern)

            type = rule.pattern[beg:end+1]
            id = self.lookup_id(type)
            if id is None:
                raise RuntimeError('unknown token type %s' % type)
            pattern += '(' + str(id) + ')'
            i = end + 1

        log.debug('%s => %s' % (rule.pattern, pattern))
        rule.re = re.compile(pattern)

    def compile_rules(self):
        for ruleset in self.rules.values():
            for rule in ruleset:
                self.compile(rule)


class Parser(RuleSet):
    """
    A class for parsing files in reduced configuration format.
    """

    def __init__(self, profile, path):
        RuleSet.__init__(self, profile, path)
        self.root = Node(Parser.nodes['root'], None, None, None)

    def parse(self):
        self.push_context('root')
        self.tokenize()
        self.enumerate_tokens()
        self.compile_rules()
        self.parse_nodes()
        self.finalize_nodes()
        self.pop_context()
        return self.root

    def parse_nodes(self):
        while self.tokenq:
            tkn = self.pull_token()
            self.parse_node(tkn, self.root)

    def finalize_nodes(self):
        self.root.finalize()

    def demand_load(self, module):
        if module not in self.nodes.keys():
            self.load_module(module)
            if module in self.nodes.keys():
                self.enumerate_tokens()
                self.compile_rules()

    def parse_node(self, node_tkn, parent):
        node_name = node_tkn.str
        log.debug('parsing node %s...' % node_name)
        self.demand_load(node_name)
        if node_name not in self.nodes.keys():
            raise RuntimeError('%s:%d: unknown node type %s' %
                               (where(node_tkn), node_name))

        self.push_context(node_name)

        nodedef = self.nodes[node_name]
        extra = self.pull_tokens(node_tkn.level, nodedef.extra_tokens)
        root = self.root
        node = nodedef.type(nodedef, root, parent, node_tkn, *extra)
        tokens = self.pull_tokens(node_tkn.level)

        log.debug('%s block: %s' %
                   (node_name, ' '.join(x.str for x in tokens)))

        while tokens:
            xlated = self.translate_tokens(tokens)
            tknstr = ' '.join(x.type for x in tokens)
            xltstr = re.sub(r' , ', ', ', ' '.join(str(x) for x in xlated))

            log.debug('%s xlated to %s' % (tknstr, xltstr))

            rule, match = self.match_rule(self.rules[node_name], xltstr)

            if rule is None:
                self.pushback_tokens(tokens[1:])
                c_tkn = tokens[0]
                c = self.parse_node(c_tkn, node)

                if c is None:
                    raise RunTimeError('%s:%d: failed to parse' % where(c_tkn))

                tokens = self.pull_tokens(node_tkn.level)
            else:
                log.debug('%s => %s (%s)' %
                           (tknstr, rule.re.pattern, rule.callback))
                n = match.count(' ') + match.count(',') + 1
                args = tokens[0:n]
                tokens = tokens[n:]
                log.debug('matched tokens %d => %s' %
                           (n, ' '.join(x.str for x in tokens)))

                c = getattr(node, rule.callback)
                if c is None:
                    RuntimeError('%s has no method %s' %
                                 (str(nodedef.type), rule.callback))
                else:
                    c(*args)

        self.pop_context()

        return node

    def match_rule(self, rules, tknstr):
        max = 0
        rule = None
        match = None
        for r in rules:
            log.debug('matching "%s" against "%s"' % (tknstr, r.re.pattern))
            m = r.re.match(tknstr)
            if m is not None:
                log.debug(' => match (%s)' % m.group(0))
                l = len(m.group(0))
                if l > max:
                    max = l
                    rule = r
                    match = m
            else:
                log.debug(' => mismatch')

        return rule, match.group(0) if match else None

    class Rule:
        """A single parser rule."""
        def __init__(self, pattern, callback):
            self.pattern = pattern
            self.callback = callback

def generate_root(nodedef, nodes, fs):
    pass

NodeDef(
    'root', None, 0,
    [],
    [Lexer.TokenRegex(r'[0-9]+'       , 'int'     ),
     Lexer.TokenRegex(r'0x[0-9a-f]+'  , 'int'     ),
     Lexer.TokenRegex(r'[0-9]+-[0-9]+', 'intrange'),
     Lexer.TokenStr  (r','            , 'comma'   ),
     Lexer.TokenStr  (r'-'            , 'dash'    ),
     Lexer.TokenRegex(r'.*'           , 'token'   )],
    [],
    generate_root
)
