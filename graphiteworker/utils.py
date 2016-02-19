#!/usr/bin/env python
# -*- coding: UTF-8 -*-

###################################################################
#
# Author: Christian Eichelmann
#
###################################################################


import os
import json
import fcntl


class Config(dict):
    """ load configuration file """

    def load(self, filename):
        self.update(json.load(open(filename, 'r')))


class PidFile(object):
    """
    Context manager that locks a pid file.  Implemented as class
    not generator because daemon.py is calling .__exit__() with no parameters
    instead of the None, None, None specified by PEP-343.
    """

    def __init__(self, path):
        self.path = path
        self.pidfile = None
        if os.path.isfile(self.path):
            raise SystemExit("pid file already exists. check if service is already running.")

    def __enter__(self):
        self.pidfile = open(self.path, "a+")
        try:
            fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise SystemExit("Already running according to %s" % (self.path, ))

        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(os.getpid()))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self.pidfile

    def __exit__(self, exc_type=None, exc_value=None, exc_tb=None):
        try:
            self.pidfile.close()
        except IOError as err:
            # ok if file was just closed elsewhere
            if err.errno != 9:
                raise
        os.remove(self.path)
