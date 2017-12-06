#!/usr/bin/env python3

from distutils.core import setup
import sys, os, glob

profiles = []
profile_dirs = glob.glob('src/profiles/*')
for p in profile_dirs:
    module_files = glob.glob(os.path.join(p, 'modules', '*.py'))
    if not module_files:
        continue
    profile = p.split('src/profiles/')[1]
    profile_dir = os.path.join(sys.prefix, 'share', 'gen-config',
                               'profiles', profile, 'modules')
    modules = [x for x in module_files]
    profiles.append((profile_dir, modules))
    print('%s: %s' % (profiles[-1][0], profiles[-1][1]))

for p in profiles:
    print('%s: %s' % (p[0], p[1]))

setup(name = 'genconfig',
      version = '0.0',
      description = 'Configuration Generator/General Configurator Framework',
      author = 'Krisztian Litkey',
      author_email = 'kli@iki.fi',
      url = 'https://github.com/klihub/gen-config.git',
      packages = ['genconfig'],
      scripts = ['src/gen-config'],
      package_dir = { 'genconfig': 'src/genconfig' },
      data_files = profiles,
)
      
