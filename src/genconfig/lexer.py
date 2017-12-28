#!/usr/bin/env python3

#
# Lexical analiser for reduced configuration parsing.
#
# The current implementation is very primitive. It is more of a
# simple tokenizer than a real lexical analiser. The tasks it
# performs are:
#
# - read the input file
# - strip comments (lines starting with #)
# - handle file inclusion (@include directive)
# - split the input into tokens
#
# A token is a whitespace separated sequence, with the exception that
# a comma is always a token of its own.

import sys, importlib, os, re
import genconfig.log as log

class TokenSet():
    """A class for handling keywords and tokens the lexer understands."""

    keywords = {}
    tokens = {}
    typetbl = {}
    idtbl = {}

    def __init__(self):
        pass

    def enumerate_tokens(self):
        next_id = 0
        what = 'keyword'
        for tknsets in [self.keywords.values(), self.tokens.values()]:
            for tknset in tknsets:
                for tkn in tknset:
                    id = self.lookup_id(tkn.type)
                    if id is None:
                        tkn.id = next_id
                        self.idtbl[tkn.type] = tkn.id
                        self.typetbl[tkn.id] = tkn.type
                        next_id += 1
                        log.debug('%s %s => #%d' % (what, tkn.type, tkn.id))
                    else:
                        tkn.id = id
            what = 'token'

    def lookup_id(self, type):
        if type in self.idtbl.keys():
            return self.idtbl[type]
        else:
            return None

    def lookup_type(self, id):
        if id in self.typetbl.keys():
            return self.typetbl[id]
        else:
            return None

    def translate_tokens(self, tokens):
        ids = []
        for tkn in tokens:
            if tkn.str in [',', '-']:
                id = tkn.str
            else:
                id = self.lookup_id(tkn.type)
                if id is None:
                    raise RuntimeError('unknown token type %s' % tkn.type)
            ids.append(id)
        return ids


class Lexer(TokenSet):
    """A class for reduced configuration lexical analysis."""

    active_keywords = []
    active_tokens = []
    regexp_type = type(re.compile(''))

    def __init__(self, profile, path):
        self.profile = profile
        self.files = []
        self.tokenq = []
        self.include_file(path)

    def tokenize(self):
        while self.files:
            input = self.files[-1]
            for tkn in input:
                if tkn.str == '@modules':
                    self.load_modules(input)
                    break
                if tkn.str == '@include':
                    path = next(input).str
                    self.include_file(path, tkn.level, input.path)
                    break
                else:
                    log.debug('+ token %s@%d' % (tkn.str, tkn.level))
                    self.tokenq.append(tkn)
            else:
                self.files.pop(-1)

    def load_module(self, name):
        profiles = [ self.profile, 'common' ]
        for p in [self.profile, 'common']:
            m = p + '.modules.' + name
            if m in sys.modules:
                return
            log.progress('looking for module %s in %s profile' % (name, p))
            try:
                sys.modules[m] = importlib.import_module(m)
                return
            except ModuleNotFoundError as e:
                pass
        raise RuntimeError('module "%s" not found in any profile' % name)

    def load_modules(self, input):
        for tkn in input:
            if tkn.level != -1:
                input.pushback(tkn)
                return
            name = tkn.str
            if name == ',':
                continue
            else:
                self.load_module(name)

    def include_file(self, path, level = 0, parent_path = None):
        if not os.path.isabs(path) and parent_path is not None:
            path = os.path.join(os.path.dirname(parent_path), path)

        for f in self.files:
            if f.path == path:
                raise RuntimeError('recusive inclusion of %s (in %s)' %
                                   (path, parent_path))

        self.files.append(Lexer.File(path, level))

    def pull_token(self, level = -1):
        if not self.tokenq:
            return None
        elif self.tokenq[0].level == -1 or level == -1:
            return self.classify(self.tokenq.pop(0))
        elif self.tokenq[0].level > level:
            return self.classify(self.tokenq.pop(0))
        else:
            return None

    def pull_tokens(self, level = -1, n = -1):
        tokens = []
        while self.tokenq and (self.tokenq[0].level > level or
                               self.tokenq[0].level < 0) and n != 0:
            n -= 1
            tokens.append(self.classify(self.tokenq.pop(0)))
        return tokens
    
    def pushback_token(self, tkn):
        tkn.type = None
        self.tokenq.insert(0, tkn)

    def pushback_tokens(self, tokens):
        for i in range(len(tokens) - 1, -1, -1):
            tokens[i].type = None
            self.tokenq.insert(0, tokens[i])

    def peek_tokens(self, n = 1):
        if n == 1:
            return self.classify(self.tokenq[0])
        else:
            return self.classify(self.tokenq[0:n])

    def classify(self, tokens):
        if type(tokens) != type([]):
            token_list = [tokens]
        else:
            token_list = tokens

        self.classify_keywords(token_list)
        self.classify_tokens(token_list)
        return tokens

    def classify_keywords(self, tokens):
        for tkn in tokens:
            if tkn.type is not None:
                continue
            for kw in self.active_keywords[-1]:
                if tkn.str == kw.match:
                    tkn.type = kw.type
                    break
            if tkn.type is not None:
                continue
            for kw in self.active_keywords[0]:
                if tkn.str == kw.match:
                    tkn.type = kw.type
                    break
            if tkn.type is not None:
                log.debug('token %s: keyword %s' % (tkn.str, tkn.type))

    def classify_tokens(self, tokens):
        for tkn in tokens:
            if tkn.type is not None:
                continue

            contexts = [self.active_tokens[-1], self.active_keywords[-1]]
            if len(self.active_tokens) > 1:
                contexts.append(self.active_tokens[0])
                contexts.append(self.active_keywords[0])

            for ctx in contexts:
                for tkndef in ctx:
                    tkndef.classify(tkn)
            if tkn.type is None:
                tkn.type = '_token_'
            if tkn.type == '_comma_':
                tkn.type = ','
            if tkn.type == '_dash_':
                tkn.type = '-'
            
            log.debug('token %s: token %s' % (tkn.str, tkn.type))

    def push_context(self, name):
        kl = self.keywords[name] if name in self.keywords.keys() else []
        tl = self.tokens[name] if name in self.tokens.keys() else []
        self.active_keywords.append(kl)
        self.active_tokens.append(tl)

    def pop_context(self):
        self.active_keywords.pop(-1)
        self.active_tokens.pop(-1)

    class TokenDef():
        """A token definition for classifying tokens."""
        def __init__(self, match, type):
            self.match = match
            pre = '' if type.startswith('_') else '_'
            suf = '' if type.endswith('_') else '_'
            self.type = pre + type + suf
            self.id = -1

        def classify(self, tkn):
            if tkn.type is not None:
                return
            if type(self.match) == type(''):
                log.debug('testing token %s with %s' % (tkn.str, self.match))
                if tkn.str == self.match:
                    tkn.type = self.type
            elif type(self.match) == Lexer.regexp_type:
                log.debug('testing token %s with %s' % (tkn.str,
                                                         self.match.pattern))

                m = self.match.match(tkn.str)
                if m is not None and m.group(0) == tkn.str:
                    tkn.type = self.type
            elif callable(self.match):
                self.match(tkn)

            if tkn.type is not None:
                #log.debug('token %s: type %s' % (tkn.str, tkn.type))
                pass

            return True if tkn.type is not None else False

    class TokenKeyword(TokenDef):
        def __init__(self, keyword):
            Lexer.TokenDef.__init__(self, keyword, keyword)

    class TokenStr(TokenDef):
        def __init__(self, match, type):
            Lexer.TokenDef.__init__(self, match, type)

    class TokenRegex(TokenDef):
        def __init__(self, match, type):
            Lexer.TokenDef.__init__(self, re.compile(match), type)

    class TokenFunc(TokenDef):
        def __init__(self, match, type):
            Lexer.TokenDef.__init__(self, match, type)

    def NoTokens():
        return []

    def Keywords(kwlist):
        tkndefs = []
        for kw in kwlist:
            tkndefs.append(Lexer.TokenKeyword(kw))
        return tkndefs

    def NoKeywords():
        return []

    class Token:
        """A single token read from the input stream."""

        def __init__(self, token, file, line, level):
            self.str = token
            self.type = None
            self.file = file
            self.line = line
            self.level = level
    
    class File:
        """A single input file, iterable for relevant input lines."""

        def __init__(self, path, level = 0):
            self.path = path
            self.level = level
            self.line = None
            self.lineno = 0
            self.input = open(self.path, 'r')
            self.pushedback = []

        def __iter__(self):
            # no concurrent/parallel iterations
            return self

        def __next__(self):
            if self.pushedback:
                return self.pushedback.pop(0)
            level = self.next_line()

            if self.line is None:
                raise StopIteration

            self.line = re.sub(r'[ \t]+', ' ', self.line)
            self.line = re.sub(r' *, *', ',', self.line)

            token_str = self.split_token()

            return Lexer.Token(token_str, self.path, self.lineno, level)

        def next_line(self):
            """Read a line, skip comments, count indentation level."""
            # we have one already, so level is a continuation
            if self.line is not None:
                return -1

            level = self.level
            for line in iter(self.input):
                self.lineno += 1
                for c in line:
                    if c == ' ':
                        level += 1
                    elif c == '\t':
                        level += 8
                    else:
                        break
                line = line.strip(' \t\n')

                if not line or line.startswith('#'):
                    continue

                self.line = line
                return level

            self.line = None
            return None

        def split_token(self):
            """Split the first token off the current input line."""
            if not self.line:
                return None, None

            token = ''
            for idx in range(0, len(self.line)):
                c = self.line[idx]
                if c == ' ':
                    self.line = self.line[idx+1:]
                    return token
                elif c == ',':
                    if idx > 0:
                        self.line = self.line[idx:]
                    else:
                        token = ','
                        self.line = self.line[1:]
                    break
                else:
                    token += c
            else:
                self.line = None

            return token

        def pushback(self, tkn):
            self.pushedback.append(tkn)
