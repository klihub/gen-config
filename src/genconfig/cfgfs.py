#!/usr/bin/env python3

import sys, os
from hashlib import sha1
import genconfig.log as log

class CfgFS:
    class File:
        def __init__(self, path, mode):
            self.path = path
            self.mode = mode
            self.csum = None
            self.buf = ''
    
        def write(self, buf, end = '\n'):
            self.buf += buf + end
            self.csum = None

        def close(self):
            pass

        def content(self):
            return self.buf

        def sha1(self):
            if not self.csum:
                buf = self.content()
                self.csum = sha1(bytearray(self.content(), 'ascii')).hexdigest()
            return self.csum

        def checkfs(self, destdir):
            try:
                with open(destdir + self.path) as f:
                    buf = f.read()
                    csum = sha1(bytearray(buf, 'ascii')).hexdigest()
                    return csum == self.sha1()
            except:
                return False

        def commit(self, destdir):
            if self.checkfs(destdir):
                log.progress('%s already up to date...' % self.path)
                return False
            else:
                path = destdir + self.path
                log.progress('writing file %s...' % path)
                os.makedirs(os.path.dirname(path), 0o755, True)
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                mode = self.mode
                fd = os.open(path, flags, mode)
                os.write(fd, bytearray(self.content(), 'ascii'))
                os.close(fd)
                return True

    class IniFile(File):
        def __init__(self, path, mode):
            self.path = path
            self.mode = mode
            self.csum = None
            self.sections = {}
            self.prevkey = None

        def write(self, buf, key=None, end='\n'):
            if not key:
                if not self.prevkey:
                    raise RuntimeError('No section key, cannot write.')
                key = self.prevkey
            else:
                self.prevkey = key
            if key not in self.sections.keys():
                self.sections[key] = buf + end
            else:
                self.sections[key] += buf + end
            self.csum = None

        def close(self):
            self.prevkey = None

        def content(self):
            nl = buf = ''
            for key, val in self.sections.items():
                buf += nl + '[' + key + ']\n' + val
                nl = '\n'
            return buf

    class Dir:
        def __init__(self, path, mode):
            self.path = path
            self.mode = mode

        def checkfs(self, destdir):
            path = destdir + self.path
            return os.access(path, os.R_OK | os.W_OK | os.X_OK)

        def commit(self, destdir):
            if self.checkfs(destdir):
                log.progress('directory %s up-to-date...' % path)
                return False
            else:
                path = destdir + self.path
                log.progress('creating directory %s...' % path)
                os.makedirs(os.path.dirname(path), 0o755, True)
                os.mkdir(path, self.mode, True)
                return True

    class Link:
        def __init__(self, src, dst, symbolic = True):
            self.src = src
            self.dst = dst
            self.symbolic = symbolic

        def checkfs(self, destdir):
            path = destdir + self.dst
            if self.symbolic:
                try:
                    src = os.readlink(path)
                    return src == self.src
                except:
                    return False
            else:
                try:
                    dst = os.stat(path)
                    src = os.stat(self.stc)
                    return src.st_dev == dst.st_dev and src.st_ino == dst.st_int
                except:
                    return False

        def commit(self, destdir):
            kind = 'symbolic ' if self.symbolic else 'hard '
            if self.checkfs(destdir):
                log.progress('%slink %s up-to-date...' % (kind, self.dst))
                return False
            else:
                path = destdir + self.dst
                log.progress('creating %slink %s -> %s...' %
                             (kind, self.src, path))
                os.makedirs(os.path.dirname(path), 0o755, True)
                if self.symbolic:
                    os.symlink(self.src, path)
                else:
                    os.link(self.src, path)
                return True


    def __init__(self):
        self.files = {}

    def mkdir(self, path, mode=0o755):
        if not os.path.isabs(path):
            raise RuntimeError('path %s is not absolute' % path)
        if path in self.files:
            d = self.files[path]
            if type(d) != CfgFS.Dir:
                raise RuntimeError('existing %s not a directory' % path)
        else:
            d = self.files[path] = CfgFS.Dir(path, mode)
        return d

    def open(self, path, ini=False, mode=0o644):
        if not os.path.isabs(path):
            raise RuntimeError('path %s is not absolute' % path)
        if path in self.files:
            f = self.files[path]
        else:
            if ini:
                f = self.files[path] = CfgFS.IniFile(path, mode)
            else:
                f = self.files[path] = CfgFS.File(path, mode)
        return f

    def link(self, src, dst, symbolic = False):
        if not os.path.isabs(dst):
            raise RuntimeError('path %s is not absolute' % dst)
        if dst in self.files:
            l = self.files[dst]
            if type(l) != CfgFS.Link or l.symbolic != symbolic:
                raise RuntimeError('cannot create %slink %s -> %s, %s exists' %
                                   ('symbolic ' if symlink else '',
                                    l.src, l.dst, l.dst))
        else:
            l = self.files[dst] = CfgFS.Link(src, dst, symbolic)
        return l

    def hardlink(self, src, dst):
        return self.link(src, dst, False)

    def symlink(self, src, dst):
        return self.link(src, dst, True)

    def create_dirs(self, destdir):
        created = False
        dirs = []
        for k, v in self.files.items():
            if type(v) == CfgFS.Dir and v not in dirs:
                dirs.append(v)
        for d in sorted(dirs, key = lambda x: x.path):
            if d.commit(destdir):
                created = True
        return created
            
    def create_symlinks(self, destdir):
        created = False
        symlinks = []
        for k, v in self.files.items():
            if type(v) == CfgFS.Link and v.symbolic and v not in symlinks:
                symlinks.append(v)
        for l in symlinks:
            if l.commit(destdir):
                created = True
        return created

    def create_files(self, destdir):
        created = False
        for k, v in self.files.items():
            if type(v) in [CfgFS.File, CfgFS.IniFile]:
                if v.commit(destdir):
                    created = True
        return created

    def commit(self, destdir = '/'):
        if not destdir.startswith('/'):
            raise RuntimeError('destdir (%s) is not absolute' % destdir)
        destdir = '/' + destdir.strip('/')
        updated = False
        if self.create_dirs(destdir):
            updated = True
        if self.create_symlinks(destdir):
            updated = True
        if self.create_files(destdir):
            updated = True
        return updated

    def checkfs(self, destdir = '/'):
        if not destdir.startswith('/'):
            raise RuntimeError('destdir (%s) is not absolute' % destdir)
        destdir = '/' + destdir.strip('/')
        for k, v in self.files.items():
            if not v.checkfs(destdir):
                return False
            else:
                log.info('%s already up to date...' % k)
        return True
        
