#
# mod-h2 test suite
# check handling of invalid chars in headers
#

import copy
import os
import re
import sys
import time
import pytest

from datetime import datetime
from TestEnv import TestEnv
from TestHttpdConf import HttpdConf

def setup_module(module):
    print("setup_module: %s" % module.__name__)
    TestEnv.init()
    HttpdConf().add_vhost_cgi().install()
    assert TestEnv.apache_restart() == 0
        
def teardown_module(module):
    print("teardown_module: %s" % module.__name__)
    assert TestEnv.apache_stop() == 0

class TestStore:

    def setup_method(self, method):
        print("setup_method: %s" % method.__name__)

    def teardown_method(self, method):
        print("teardown_method: %s" % method.__name__)

    # let the hecho.py CGI echo chars < 0x20 in field name
    # for almost all such characters, the stream gets aborted with a h2 error and 
    # there will be no http status, cr and lf are handled special
    def test_200_01(self):
        url = TestEnv.mkurl("https", "cgi", "/hecho.py")
        for x in range(1, 32):
            r = TestEnv.curl_post_data(url, "name=x%%%02xx&value=yz" % x)
            if x in [ 10 ]:
                assert 0 == r["rv"], "unexpected exit code for char 0x%02x" % x
                assert 500 == r["response"]["status"], "unexpected status for char 0x%02x" % x
            elif x in [ 13 ]:
                assert 0 == r["rv"], "unexpected exit code for char 0x%02x" % x
                assert 200 == r["response"]["status"], "unexpected status for char 0x%02x" % x
            else:
                assert 0 != r["rv"], "unexpected exit code for char 0x%02x" % x

    # let the hecho.py CGI echo chars < 0x20 in field value
    # for almost all such characters, the stream gets aborted with a h2 error and 
    # there will be no http status, cr and lf are handled special
    def test_200_02(self):
        url = TestEnv.mkurl("https", "cgi", "/hecho.py")
        for x in range(1, 32):
            if 9 != x:
                r = TestEnv.curl_post_data(url, "name=x&value=y%%%02x" % x)
                if x in [ 10, 13 ]:
                    assert 0 == r["rv"], "unexpected exit code for char 0x%02x" % x
                    assert 200 == r["response"]["status"], "unexpected status for char 0x%02x" % x
                else:
                    assert 0 != r["rv"], "unexpected exit code for char 0x%02x" % x


    # let the hecho.py CGI echo 0x10 and 0x7f in field name and value
    def test_200_03(self):
        url = TestEnv.mkurl("https", "cgi", "/hecho.py")
        for hex in [ "10", "7f" ]:
            r = TestEnv.curl_post_data(url, "name=x%%%s&value=yz" % hex)
            assert 0 != r["rv"]
            r = TestEnv.curl_post_data(url, "name=x&value=y%%%sz" % hex)
            assert 0 != r["rv"]
    
    # test header field lengths check, LimitRequestLine (default 8190)
    def test_200_10(self):
        url = TestEnv.mkurl("https", "cgi", "/")
        val = "1234567890" # 10 chars
        for i in range(3): # make a 10000 char string
            val = "%s%s%s%s%s%s%s%s%s%s" % (val, val, val, val, val, val, val, val, val, val)
         # LimitRequestLine 8190 ok, one more char -> 431
        r = TestEnv.curl_get(url, options=[ "-H", "x: %s" % (val[:8187]) ])
        assert 200 == r["response"]["status"]
        r = TestEnv.curl_get(url, options=[ "-H", "x: %sx" % (val[:8188]) ])
        assert 431 == r["response"]["status"]

    # test header field lengths check, LimitRequestFieldSize (default 8190)
    def test_200_11(self):
        url = TestEnv.mkurl("https", "cgi", "/")
        val = "1234567890" # 10 chars
        for i in range(3): # make a 10000 char string
            val = "%s%s%s%s%s%s%s%s%s%s" % (val, val, val, val, val, val, val, val, val, val)
         # LimitRequestFieldSize 8190 ok, one more char -> 400 in HTTP/1.1
         # (we send 4000+4188 since they are concatenated by ", "
        r = TestEnv.curl_get(url, options=[ "-H", "x: %s" % (val[:4000]),  "-H", "x: %s" % (val[:4188]) ])
        assert 200 == r["response"]["status"]
        r = TestEnv.curl_get(url, options=[ "--http1.1", "-H", "x: %s" % (val[:4000]),  "-H", "x: %s" % (val[:4189]) ])
        assert 400 == r["response"]["status"]
        r = TestEnv.curl_get(url, options=[ "-H", "x: %s" % (val[:4000]),  "-H", "x: %s" % (val[:4191]) ])
        assert 431 == r["response"]["status"]

    # test header field lengths check, LimitRequestFields (default 100)
    def test_200_12(self):
        url = TestEnv.mkurl("https", "cgi", "/")
        opt=[]
        for i in range(98): # curl sends 2 headers itself (user-agent and accept)
            opt += [ "-H", "x: 1" ]
        r = TestEnv.curl_get(url, options=opt)
        assert 200 == r["response"]["status"]
        r = TestEnv.curl_get(url, options=(opt + [ "-H", "y: 2" ]))
        assert 431 == r["response"]["status"]

