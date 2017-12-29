#!/usr/bin/env python3

from distutils.core import setup
import sys, os, glob

data_files = []
profile_dirs = glob.glob('src/profiles/*')
for p in profile_dirs:
    module_files = glob.glob(os.path.join(p, 'modules', '*.py'))
    if not module_files:
        continue
    profile = p.split('src/profiles/')[1]
    profile_dir = os.path.join('share', 'gen-config',
                               'profiles', profile, 'modules')
    modules = [x for x in module_files]
    data_files.append((profile_dir, modules))

hook_dst = os.path.join('share', 'gen-config', 'hooks')
hook_src = os.path.join('src', 'hooks')
hooks = glob.glob(os.path.join(hook_src, '???*'))
if hooks:
    data_files.append((hook_dst, hooks))

service_dst = os.path.join('lib', 'systemd', 'system')
service_src = os.path.join('src', 'systemd')
services = glob.glob(os.path.join(service_src, '*.service'))
if services:
    data_files.append((service_dst, services))

for df in data_files:
    print('data file set %s: %s' % (df[0], df[1]))

setup(name = 'genconfig',
      version = '0.0',
      description = 'Configuration Generator/General Configurator Framework',
      author = 'Krisztian Litkey',
      author_email = 'kli@iki.fi',
      url = 'https://github.com/klihub/gen-config.git',
      packages = ['genconfig'],
      scripts = ['src/gen-config'],
      package_dir = { 'genconfig': 'src/genconfig' },
      data_files = data_files,
)

