#!/usr/bin/env python3

import sys, os, argparse
import genconfig.log as log
import genconfig.parser as parser
import genconfig.cfgfs as cfgfs

DESCRIPTION = '''
Reads a configuration file in reduced configuration syntax and generates
the corresponding set of standard component-specific full configuration
files.
'''

HELP_CONFIG  = 'reduced configuration file to process'
HELP_PROFILE = 'configuration profile to use'
HELP_DESTDIR = 'directory to generate configuration in'
HELP_VERBOSE = 'increase logging verbosity'
HELP_DEBUG   = 'enable debugging for given site'


class Cfg:
    """
    The internal representation of the configuration.
    """

    DEFAULT_PROFILE = 'gateway'

    def __init__(self, dir, argv):
        self.dir = dir
        self.parse_cmdline(argv)
        self.config_file = self.args.config_file
        self.dest_dir = self.args.destdir
        self.profile = self.args.profile

        if self.args.verbose is not None:
            for i in range(0, self.args.verbose):
                log.Logger.log_mask <<= 1
                log.Logger.log_mask |= 0x1
            log.Logger.log_mask &= ~(0x1 << log.Logger.LOG_DEBUG)

        if self.args.debug is not None:
            if None in self.args.debug:
                log.debug_enable('*')
            else:
                for site in self.args.debug:
                    for s in site.split(','):
                        log.debug_enable(s)

        sys.path.insert(0, os.path.join(self.dir, 'profiles'))
        print('added load path %s' % os.path.join(self.dir, 'profiles'))

        self.parser = parser.Parser(self.profile, self.config_file)
        self.cfgfs = cfgfs.CfgFS()

    def parse_cmdline(self, argv):
        ap = argparse.ArgumentParser(prog = argv[0], description = DESCRIPTION)
        ap.add_argument('config_file'    , help = HELP_CONFIG)
        ap.add_argument('-v', '--verbose', help = HELP_VERBOSE,
                        action = 'count')
        ap.add_argument('-d', '--debug'  , help = HELP_DEBUG,
                        action = 'append', nargs = '?', const = None)
        ap.add_argument('-P', '--profile', help = HELP_PROFILE,
                        default = Cfg.DEFAULT_PROFILE)
        ap.add_argument('-D', '--destdir', help = HELP_DESTDIR, default = None)
        self.args = ap.parse_args(argv[1:])
        if not self.args.destdir:
            base = os.path.basename(self.args.config_file).split('.')[0]
            self.args.destdir = os.path.abspath('out/%s/%s' %
                                                (base, self.args.profile))

    def parse(self):
        self.cfg = self.parser.parse()

    def dump(self):
        self.cfg.dump()

    def generate(self):
        for name, nodedef in self.parser.nodes.items():
            nodedef.generate_config(self.cfgfs)

    def write(self):
        return self.cfgfs.commit(self.args.destdir)

    def checkfs(self):
        return self.cfgfs.checkfs(self.args.destdir)
