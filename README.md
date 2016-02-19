## About

This is a [Gearman](http://gearman.org/) Worker that is designed to use the nagios performance data generated and published by the awesome Nagios-Plugin [Mod-Gearman](http://mod-gearman.org/) and feed them into [Graphite](http://graphite.wikidot.com/) or anything that understands one of the Graphite-Protocols.

Since it is a worker you can scale it as you like by using a larger pool (processes that are spawned on the machine running the graphiteworker) or by starting it on a many machines as you like. It only opens one connection to graphite and sends all data arriving in Germans perfdata queue. You can choose if you want to use the line or the pickle protocol. Since graphite works best with the line protocol I suggest you to use it to feed your data.

## Installing

```bash
$ git clone https://github.com/Crapworks/graphiteworker.git
$ cd graphiteworker
$ sudo pip install -r requirements.txt
$ sudo python setup.py install
```

## Configuration

The worker is configured via the `worker.json` configuration file. Find it unter `/etc/graphite_worker/worker.json`. It is a json file with the following configuration keys:

**gearman\_job\_servers**

> The hostname of the Gearman job server who holds the perfdata queue from Nagios/Icinga

**gearman\_key**

> Secret key for encrypting the transmitted data

**client\_id**

> Name with which the worker registers at the Gearman job server

**graphite\_host**

> Hostname of your graphite server

**graphite\_port**

> port of your carbon listener

**graphite\_protocol**

> Protocol to use. Options: 'plain' to use graphites line protocol (recommended) or 'pickle' to use the pickle protocol

**pool\_size**

> number of processes that should be spawned

## Running

```bash
$ /etc/init.d/graphite_worker start
```
