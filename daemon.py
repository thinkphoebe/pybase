# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jun 27, 2014
'''

import sys
import os
import time
import atexit
import signal


class Daemon:
    def __init__(self, pidfile, stderr='/tmp/daemon_err.log', stdout='/tmp/daemon_out.log', stdin='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def _daemonize(self):
        # 脱离父进程
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # 脱离终端
        os.setsid()

        # 修改当前工作目录
        os.chdir("/")

        # 重设文件创建权限
        os.umask(0)

        # 第二次fork，禁止进程重新打开控制终端
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)

        # 重定向标准输入/输出/错误
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # 注册程序退出时的函数，即删掉pid文件
        atexit.register(self.delpid)
        pid = str(os.getpid())
        file(self.pidfile, 'w+').write("%s\n" % pid)

    def delpid(self):
        os.remove(self.pidfile)

    def start(self):
        """
        start the daemon
        """
        # check for a pidfile to see if the daemon already runs
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if pid:
            if os.path.isdir('/proc/%d' % pid):
                sys.stderr.write("pidfile %s already exist and progress running\n" % self.pidfile)
                sys.exit(1)
            else:
                sys.stderr.write("pidfile %s exist and progress not running, call killpg and remove pidfile\n" % self.pidfile)
                try:
                    os.killpg(pid, signal.SIGKILL)
                    self.delpid()
                except OSError:
                    pass

        # Start the daemon
        self._daemonize()
        self._run()

    def stop(self):
        # Get the pid from the pidfile
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if not pid:
            message = "pidfile %s does not exist. daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return  # not an error in a restart

        if os.path.isdir('/proc/%s' % pid):
            print('sending signal usr1 to notation child process to exit, wait 30s...')
            for i in range(30):
                try:
                    os.kill(pid, signal.SIGUSR1)
                except OSError as err:
                    err = str(err).lower()
                    if err.find("no such process") > 0:
                        print('child process existed')
                        break
                time.sleep(1)
                print('%d ...' % i)

        # Try killing the daemon process group
        try:
            while 1:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
        except OSError as err:
            err = str(err).lower()
            if err.find("no such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print(str(err))
                sys.exit(1)

    def restart(self):
        self.stop()
        self.start()

    def _run(self):
        pass


class DaemonTest(Daemon):
    def __init__(self, pidfile):
        Daemon.__init__(self, pidfile)

    def _run(self):
        while True:
            print("begin sleep")
            time.sleep(20)
            print("end sleep")


if __name__ == "__main__":
    daemon = DaemonTest('/tmp/daemon-example.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            print('start daemon')
            daemon.start()
        elif 'stop' == sys.argv[1]:
            print('stop daemon')
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            print('restart daemon')
            daemon.restart()
        else:
            print("Unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        print("usage: %s start|stop|restart" % sys.argv[0])
        sys.exit(2)
