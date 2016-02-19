#!/usr/bin/env python

from setuptools import setup
from graphiteworker import __version__, __author__

setup(name='graphite-worker',
    # version / author informations
    version=__version__,
    author=__author__,
    author_email='github@crapworks.de',

    # description
    description='A mod-gearman worker for feeding perfdata to graphite',
    long_description='''
    graphite_worker is a worker for the mod-gearman perfdata queue. It reads
    nagios performance data from the gearman queue and feeds it to graphite
    either with the plaintext or pickle protocol.
    ''',

    # fork me on github
    url='https://github.com/Crapworks/graphite_worker',

    # non-development dependencies
    install_requires=['argparse>=1.2', 'gearman>=2.0', 'python-daemon>=1.5'],

    # install this package
    packages=['graphiteworker'],

    # this is not part of the module
    scripts=['graphite_worker'],

    # install init script and config file
    data_files=[
        ('/etc/init.d', ['data/graphite_worker']),
        ('/etc/graphite_worker', ['data/worker.json'])
    ]
)
