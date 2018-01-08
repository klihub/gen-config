#!/usr/bin/env python3

import re, inspect

class Logger:
    LOG_FATAL = 0
    LOG_ERROR = 1
    LOG_WARNING = 2
    LOG_PROGRESS = 3
    LOG_INFO = 4
    LOG_NOTE = 5
    LOG_DEBUG = 6

    default_levels = [LOG_WARNING, LOG_PROGRESS]
    debug_contexts = []
    
    log_prefix = {
        LOG_FATAL: 'fatal error: ',
        LOG_ERROR: 'E: ',
        LOG_WARNING: 'W: ',
        LOG_PROGRESS: '',
        LOG_INFO: '',
        LOG_NOTE: '',
        LOG_DEBUG: 'D: '
    }

    log_unmaskable = (1 << LOG_FATAL) | (1 << LOG_ERROR)
    log_mask = log_unmaskable | (1 << LOG_WARNING)
    
    def __init__(self, levels = default_levels):
        log_set_mask(levels)

def set_mask(levels):
    Logger.log_mask |= Logger.log_unmaskable

    if type(levels) == type([]):
        for l in levels:
            Logger.log_mask |= 1 << l
    else:
        Logger.log_mask |= 1 << levels


def log(level, msg):
    if Logger.log_mask & (1 << level):
        prefix = Logger.log_prefix[level]
        print('%s%s' % (prefix, msg))

def fatal(self, msg):
    log(LOG_FATAL, msg)
    sys.exit(1)
    
def error(msg):
    log(Logger.LOG_ERROR, msg)

def warning(msg):
    log(Logger.LOG_WARNING, msg)

def progress(msg):
    log(Logger.LOG_PROGRESS, msg)

def info(msg):
    log(Logger.LOG_INFO, msg)

def note(msg):
    log(Logger.LOG_NOTE, msg)


def debug_enable(contexts):
    if type(contexts) == type(''):
        contexts = re.sub(' *', '', contexts).split(',')
    Logger.debug_contexts = list(set(Logger.debug_contexts + contexts))
    set_mask(Logger.LOG_DEBUG)

    
def debug_enabled(contexts):
    if not Logger.log_mask & (1 << Logger.LOG_DEBUG):
        return False
    if not contexts or not Logger.debug_contexts:
        return True
    if '*' in Logger.debug_contexts or 'all' in Logger.debug_contexts:
        return True
    for c in contexts:
        if c in Logger.debug_contexts:
            return True
    return False


def debug(*args):
    caller = inspect.stack()[1][3]
    if caller == 'debug':
        caller = inspect.stack()[2][3]
    if type(args[0]) == type(''):
        contexts = [caller]
        msg = args[0]
    else:
        contexts = args[0]
        msg = args[1]
        contexts.insert(0, caller)
    
    if debug_enabled(contexts):
        log(Logger.LOG_DEBUG, '[%s] %s' % (caller, msg))

set_mask(Logger.default_levels)

