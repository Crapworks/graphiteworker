#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import unittest
from graphiteworker.graphite_worker import NormalizedPerfData

PERF1="""
DATATYPE::SERVICEPERFDATA\tTIMET::1359642046\tHOSTNAME::test-host01.example.com\tSERVICEDESC::MySQL Index Usage\tSERVICEPERFDATA::index_usage=57.72%;90:;80: index_usage_now=0.00%\tSERVICECHECKCOMMAND::check_mysql_health!$_HOSTDBUSER!$_HOSTDBPASS!$_HOSTDBSCHEMA!index-usage\tSERVICESTATE::2 SERVICESTATETYPE::1
"""

PERF2 = """
DATATYPE::HOSTPERFDATA\tTIMET::1359642046\tHOSTNAME::test-host01.example.com\tHOSTPERFDATA::rta=0.562000ms;5000.000000;5000.000000;0.000000 pl=0%;100;100;0\tHOSTCHECKCOMMAND::check-host-alive!(null)\tHOSTSTATE::0\tHOSTSTATETYPE::1
"""

PERF3 = """
DATATYPE::SERVICEPERFDATA\tTIMET::1359642046\tHOSTNAME::test-host01.example.com\tSERVICEDESC::Apache Middleware Status\tSERVICEPERFDATA::time=0.074175s;;;0.000000 size=431B;;;0\tSERVICECHECKCOMMAND::check_http!-s ok\tSERVICESTATE::0\tSERVICESTATETYPE::1
"""

PERF4 = """
DATATYPE::SERVICEPERFDATA\tTIMET::1359642046\tHOSTNAME::test-host01.example.com\tSERVICEDESC::Memory\tSERVICEPERFDATA::TOTAL=8197880KB;;;; USED=6711412KB;;;; FREE=1486468KB;;;; CACHES=901864KB;;;;\tSERVICECHECKCOMMAND::check_nrpe!check_mem!10\!5\tSERVICESTATE::0 SERVICESTATETYPE::1
"""

class GraphiteWorkerParserTest(unittest.TestCase):
    """
    This is the unittest for the graphite_worker NormalizedPerfData
    parser for nagios perdata via gearman
    """

    def setUp(self):
        """ initialize some example perfdata values """

        self.perfdata = []
        self.perfdata.append(PERF1)
        self.perfdata.append(PERF2)
        self.perfdata.append(PERF3)
        self.perfdata.append(PERF4)

        self.valid_timestamps = [1359642046, 1359642046, 1359642046, 1359642046, 1359642046, 1359642046, 1359642046, 1359642046, 1359642046, 1359642046]
        self.valid_values = [0.00, 57.72, 0.000562, 0, 431.0, 0.074175, 8394629120.0, 6872485888.0, 1522143232.0, 923508736.0]

    def tearDown(self):
        """ Cleans up the test environment """
        pass

    def testNormalizedPerfData(self):
        """ Test the Perfdata parser """
        for perfdata in self.perfdata:
            result = NormalizedPerfData(perfdata)
            for metric in result:
                print metric
                self.assertTrue(metric.path.startswith('monitoring.test-host01_example_com.'))
                self.assertTrue(metric.path.endswith('.value'))
                self.assertTrue(int(metric.timestamp) in self.valid_timestamps)
                self.assertTrue(float(metric.value) in self.valid_values)

if __name__ == "__main__":
    unittest.main()
