# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 14, 2014
'''
import subprocess
import threading
import time

import log
logger = log.get_logger('utils')


def check_output_timeout(url, timeout=10):
    class ThreadRun(threading.Thread):
        def __init__(self):
            super(ThreadRun, self).__init__()
            self.output = None

        def run(self):
            self.output = subprocess.check_output(url, stderr=subprocess.STDOUT)

    thrd_run = ThreadRun()
    thrd_run.start()
    while not thrd_run.output and timeout > 0:
        time.sleep(0.1)
        timeout -= 0.1
    try:
        thrd_run.proc.terminate()
    except:
        pass

    return thrd_run.output
