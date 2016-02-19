#!/usr/bin/env python
# -*- coding: UTF-8 -*-

###################################################################
#
# Author: Christian Eichelmann
#
###################################################################


import os
import re
import sys
import shlex
import struct
import pickle
import socket
import signal
import daemon
import argparse
import logging
import logging.handlers
logger = logging.getLogger('graphite_worker')

# only needed if AMPQ transport is enabled
try:
    import pika
except ImportError:
    pika = None

from multiprocessing import Process
from gearman import GearmanWorker, DataEncoder
from gearman.errors import ServerUnavailable
from base64 import b64decode, b64encode
from rijndael import Rijndael
from utils import PidFile, Config
from time import time, sleep
from pwd import getpwnam
from grp import getgrnam

from . import __version__

config = Config()


class ModGearmanEncoder(DataEncoder):
    """
    ModGearmanEncoder - uses the Rijndael algorithm to encode/decode
    mod-gearman job data
    """

    @classmethod
    def encode(cls, encodable_object):
        return b64encode(str(encodable_object))

    @classmethod
    def decode(cls, decodable_string):
        key = config['gearman_key']

        padded_key = key.ljust(32, '\0')
        rij = Rijndael(padded_key)

        return rij.decrypt(b64decode(decodable_string))


class GraphiteGearmanWorker(GearmanWorker):
    """
    GraphiteGearmanWorker - implements a GearmanWorker class which uses the
    ModGearmanEncoder class as data encoder
    """

    data_encoder = ModGearmanEncoder

    def after_poll(self, activity):
        return True


class NormalizedPerfMetric(object):
    """
    NormalizedPerfMetric - generates a graphite data string out of
    normalized nagios perfdata. can also be used to create pickleble
    tuples to feed graphites pickle protocol

    @host: hostname of this metric
    @service: servicename of this metric
    @timestamp: timestamp of the received metric
    @key: metric key name
    @value: value of this metric (which will be normalized)
    """

    # nagios perfdata suffixes
    _suffixes = {
        'B': 1024**0, 'KB': 1024**1, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4, 'PB': 1024**5, 'EB': 1024**6,
        'K': 1000**1, 'M': 1000**2, 'G': 1000**3, 'T': 1000**4, 'P': 1000**5, 'E': 1000**6,
        's': 10**0, 'ms': 10**(-3), 'us': 10**(-6)
    }

    def __init__(self, host, service, timestamp, key, value):
        self.regex = re.compile('(?P<value>^[\d\.\-]+)(?P<unit>[\w\%]+)?(;)?.*')
        self.path = "monitoring.%s.%s.%s.value" % (self._format_key(host), self._format_key(service), self._format_key(key))
        self.value = self._format_value(value)
        self.timestamp = timestamp

    def tuple(self):
        return (self.path, (self.timestamp, self.value))

    def __str__(self):
        return "%s %s %s\n" % (self.path, self.value, self.timestamp)

    def _format_value(self, value):
        value = value.rstrip('\0').rstrip('\n')
        tmp = self.regex.search(value)
        try:
            data = tmp.groupdict()
        except:
            logger.warn("unable to parse perfdata: %s" % (value, ))
        else:
            if data['unit'] in self._suffixes:
                return str(float(data['value']) * self._suffixes[data['unit']])
            else:
                return data['value']

    def _format_key(sefl, key):
        key = key.rstrip('\0').rstrip('\n')
        key = key.lower()
        key = key.replace('/', '_slsh_')
        key = key.replace('.', '_')
        key = key.replace(' ', '_')
        key = key.strip('\'')
        key = key.strip('"')
        return key


class NormalizedPerfData(list):
    """
    NormalizedPerfData - a nagios perfdata parser, which yields the converted metrics
    in a graphite understandable format
    @perfdata = plain perfdata string reveiced via the gearman perfdata queue
    """

    mapping = {
        'TIMET': 'timestamp',
        'HOSTNAME': 'host',
        'SERVICEDESC': 'service',
        'SERVICESTATE': 'status',
        'HOSTSTATE': 'status',
        'SERVICEPERFDATA': 'perf',
        'HOSTPERFDATA': 'perf'
    }

    def __init__(self, perfdata):
        list.__init__(self)
        self.parse(perfdata.strip().split('\t'))

    def __str__(self):
        return "".join(str(metric) for metric in self)

    def tuple(self):
        return [metric.tuple() for metric in self]

    def pickle(self):
        payload = pickle.dumps(self.tuple())
        return struct.pack("!L", len(payload)) + payload

    def parse(self, tokens):
        logdata = {}

        for nvpair in tokens:
            (key, value) = nvpair.split('::', 1)

            try:
                key = self.mapping[key]
            except KeyError:
                pass

            if key == 'perf':
                value = dict([v.split('=') for v in shlex.split(value)])

            logdata[key] = value

        if 'perf' not in logdata or 'host' not in logdata or 'status' not in logdata:
            return []

        if 'timestamp' not in logdata:
            logdata['timestamp'] = time()

        if 'service' not in logdata:
            logdata['service'] = 'host'

        for key, value in logdata['perf'].iteritems():
            self.append(NormalizedPerfMetric(logdata['host'], logdata['service'], logdata['timestamp'], key, value))


class GraphiteWorker(Process):
    """
    GraphiteWorker - handles the gearman job queue and the transmission to
    the graphite server. also takes care about error situations
    """

    def __init__(self):
        Process.__init__(self)
        self.worker = GraphiteGearmanWorker(config['gearman_job_servers'])
        self._get_new_connection()
        self.worker.set_client_id(str(config['client_id']))
        self.worker.register_task('perfdata', self.process_perfdata)

    def _get_new_connection(self):
        try:
            self.socket.close()
        except:
            pass

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((config['graphite_host'], int(config['graphite_port'])))

    def process_perfdata(self, worker, job):
        try:
            perfdata = NormalizedPerfData(job.data)
            if config['graphite_protocol'] == 'plain':
                self.socket.send(str(perfdata))
            elif config['graphite_protocol'] == 'pickle':
                self.socket.send(perfdata.pickle())
        except socket.error as err:
            logger.warn("connection to graphite server lost: %s" % (str(err), ))
            sleep(1)
            logger.warn("reconnecting to graphite server...")
            self._get_new_connection()
        except Exception, err:
            logger.warn("error while processing perfdata: %s" % (str(err), ))

    def _exit(self, signum, frame):
        os._exit(-signum)

    def run(self):
        # ignore interrup signal - let the parent proccess handle it
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, self._exit)

        logger.info("started worker process with pid: %d" % (os.getpid(), ))
        while True:
            try:
                self.worker.work()
            except ServerUnavailable:
                logger.warn("lost connection to gearman job server. retrying in 1 sec.")
                sleep(1)


class GraphiteWorkerPool(object):
    """
    GraphiteWorkerPool - handles a pool of graphite worker processes
    @pool_size: number of parallel worker processes
    @user: username to drop privilges to
    @group: groupname to drop privilges to
    """

    def __init__(self, pool_size, user, group):
        self.user = user
        self.group = group
        self.pool_size = pool_size

    def _init_worker(self):
        self.worker_pool = [GraphiteWorker() for _ in range(self.pool_size)]

    def _drop_privileges(self):
        if os.getuid() != 0:
            # we are not root, so we cant drop privs
            logger.warn("we are not starting up as root. this should be impossible!")
            return

        # get uid/gid of user we want to become
        uid = getpwnam(self.user).pw_uid
        gid = getgrnam(self.group).gr_gid

        # try setting the uid
        try:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
        except:
            logger.warn("unable to drop privileges to %s:%s [%d:%d]" % (self.user, self.group, uid, gid))
        else:
            logger.debug("successfully dropped privileges to %s:%s [%d:%d]" % (self.user, self.group, uid, gid))

    def work(self):
        self._init_worker()
        self._drop_privileges()
        self.running = True
        for worker in self.worker_pool:
            worker.daemon = True
            worker.start()

        self._watchdog()

    def cleanup(self, signum, frame):
        logger.info("cleaning up. waiting for childs to exit...")
        self.stop()

    def stop(self):
        self.running = False

    def _watchdog(self):
        while self.running:
            for worker in self.worker_pool[:]:
                if not self.running:
                    break
                if worker.is_alive():
                    worker.join(1)
                else:
                    logger.warn("worker with pid %d died" % (worker.pid, ))
                    # remove dead worker
                    self.worker_pool.remove(worker)
                    # create and start new worker
                    new_worker = GraphiteWorker()
                    new_worker.daemon = True
                    new_worker.start()
                    # add new worker to pool
                    self.worker_pool.append(new_worker)

        # kill all remaining processes
        for worker in self.worker_pool:
            if worker.is_alive():
                logger.debug("terminating worker with pid: %d" % (worker.pid, ))
                worker.terminate()

        # wait for all workers to finish
        for worker in self.worker_pool:
            if worker.is_alive():
                worker.join()


def setup_logging():
    global logger
    logger.setLevel(logging.DEBUG)

    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    screen_handler = logging.StreamHandler()

    syslog_formatter = logging.Formatter('%(name)s[%(process)d]: %(levelname)s: %(message)s')
    syslog_handler.setFormatter(syslog_formatter)

    logger.addHandler(syslog_handler)
    logger.addHandler(screen_handler)


def install_signal_handler(worker_pool):
    signal.signal(signal.SIGINT, worker_pool.cleanup)
    signal.signal(signal.SIGTERM, worker_pool.cleanup)


def main(argv):
    # setup logging
    setup_logging()

    # parse command line arguemnts
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=__version__)
    parser.add_argument("-f", "--foreground", action="store_true", help="run in foreground / do not daemonize")
    parser.add_argument("-c", "--config", help="path to the configuration file", default="/etc/graphite_worker/worker.json")
    parser.add_argument("-u", "--user", help="run as specific user (default: nobody)", default="nobody")
    parser.add_argument("-g", "--group", help="run as specific group (default: nogroup)", default="nogroup")
    parser.add_argument("-p", "--pidfile", help="place for pidfile", default="/var/run/graphite_worker.pid")
    args = parser.parse_args(args=argv)

    # only root can run this program
    if os.getuid() != 0:
        raise SystemError("you need to be root to run this program")

    # try to read configuration
    try:
        global config
        config.load(args.config)
    except Exception as err:
        logger.error("unable to read config file (%s): %s" % (args.config, str(err)))
        sys.exit(1)

    # create worker instance
    worker_pool = GraphiteWorkerPool(config['pool_size'], user=args.user, group=args.group)

    # install signal handler
    install_signal_handler(worker_pool)

    # run in foreground
    if args.foreground:
        worker_pool.work()
    else:
        # daemonize
        with daemon.DaemonContext(pidfile=PidFile(args.pidfile)):
            worker_pool.work()


if __name__ == '__main__':
    main(sys.argv[1:])
