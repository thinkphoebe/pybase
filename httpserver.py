# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 1, 2014
'''
import time
import threading
import BaseHTTPServer
import SocketServer
import urllib2
import urlparse
import json

import log
logger = log.get_logger('httpserver')


class _request_handler(BaseHTTPServer.BaseHTTPRequestHandler):

    # redirect log message to logger
    def log_message(self, args, *vargs):
        logger.info("HTTPSERVER - %s", args % vargs)

    def do_GET(self):
        parsed_path = urlparse.urlparse(self.path)
        if self.server.handlers_get is None or parsed_path.path not in self.server.handlers_get:
            self.send_response(404)
            self.end_headers()
            return
        self.server.handlers_get[parsed_path.path](self)

    def do_POST(self):
        parsed_path = urlparse.urlparse(self.path)
        if self.server.handlers_post is None or parsed_path.path not in self.server.handlers_post:
            self.send_response(404)
            self.end_headers()
            return
        self.server.handlers_post[parsed_path.path](self)


class _threaded_httpserver(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):

    # force stop handler threads on server thread exit
    daemon_threads = True

    allow_reuse_address = True

    def set_handlers(self, handlers_get, handlers_post):
        self.handlers_get = handlers_get
        self.handlers_post = handlers_post

    def set_stopflag(self, value):
        self.stopflag = value


def _handler_thread(server):
    while server._status == 1:
        server._server.handle_request()

    if server._status != 2:
        logger.error('invalid status: %d' % server._status)

    logger.info('exit, wait for handlers')
    time.sleep(0.5)
    logger.info('wait complete')

    server._status = 3


class httpserver():
    '''
    可以给每个路径单独注册处理函数的http服务器。
    注册处理函数时需确保服务器处于stop状态。
    对于每个请求用单独的线程处理。
    为确保处理线程不在服务器stop时被杀死，应检查request_handler.server.stopflag自行退出
    '''

    def __init__(self):
        logger.info('...')
        self._status = 0  # 0->idle, 1->running, 2->stopping, 3->stopped
        self._server = None
        self._serve_thrd = None
        self._handlers_get = dict()
        self._handlers_post = dict()
        self._host = None
        self._port = None

    def start(self, host, port):
        logger.info('host:%s, port:%d, status:%d' % (host, port, self._status))
        if self._status != 0:
            logger.error('invalid status:%d' % self._status)
            return
        self._server = _threaded_httpserver((host, port), _request_handler)
        self._server.set_handlers(self._handlers_get, self._handlers_post)
        self._server.set_stopflag(False)
        self._status = 1
        self._serve_thrd = threading.Thread(target=_handler_thread, args=(self,))
        self._serve_thrd.start()

    def stop(self):
        logger.info('status:%d' % self._status)
        if self._status != 1:
            logger.error('invalid status:%d' % self._status)
            return
        self._server.set_stopflag(True)
        self._status = 2

        # make a dummy request, otherwise 'server._server.handle_request()'
        # in '_handler_thread' will ends until next request in.
        host, port = self._server.socket.getsockname()[:2]
        try:
            urllib2.urlopen('http://%s:%s' % (host, port))
        except:
            pass

        logger.info('wait server stop...')
        while self._status != 3:
            time.sleep(0.1)
        logger.info('server stop ok')
        self._serve_thrd.join(1)
        self._status = 0

    def register_get(self, path, handler):
        if self._status != 0:
            logger.error('invalid status:%d' % self._status)
            return
        if path in self._handlers_get:
            logger.warn('"%s" already registered by %s' % (path, self._handlers_get[path]).__str__())
        self._handlers_get[path] = handler
        logger.info('register handler (%s) to get (%s) OK' % (handler.__str__(), path))

    def unregister_get(self, path):
        if self._status != 0:
            logger.error('invalid status:%d' % self._status)
            return
        if path not in self._handlers_get:
            logger.error('path (%s) not found' % path)
            return
        handler = self._handlers_get.pop(path)
        logger.info('unregister handler (%s) to get (%s)' % (handler.__str__(), path))

    def register_post(self, path, handler):
        if self._status != 0:
            logger.error('invalid status:%d' % self._status)
            return
        if path in self._handlers_post:
            logger.warn('"%s" already registered by %s' % (path, self._handlers_post[path]).__str__())
        self._handlers_post[path] = handler
        logger.info('register handler (%s) to post (%s) OK' % (handler.__str__(), path))

    def unregister_post(self, path):
        if self._status != 0:
            logger.error('invalid status:%d' % self._status)
            return
        if path not in self._handlers_post:
            logger.error('path (%s) not found' % path)
            return
        handler = self._handlers_post.pop(path)
        logger.info('unregister handler (%s) to get (%s)' % (handler.__str__(), path))


# ================================ some utility functions  ========================================

def read_post(request_handler):
    try:
        return (True, request_handler.rfile.read(int(request_handler.headers['content-length'])))
    except Exception, e:
        logger.exception('got exception:')
        return (False, e.__str__())


def write_response(request_handler, code=200, msg=''):
    try:
        request_handler.send_response(code)
        request_handler.send_header('Content-Length', len(msg))
        request_handler.end_headers()
        request_handler.wfile.write(msg)
        return True
    except:
        logger.exception('got exception:')
        return False


def handle_json_post(request_handler, handle_function):
    result, msg = read_post(request_handler)
    code = 200
    jobj = dict()

    if result:
        try:
            request = json.loads(msg)
            logger.debug('request for %s:%s' % (handle_function.__str__(), json.dumps(request, indent=2)))
            jobj = handle_function(request)
        except Exception, e:
            code = 400
            jobj['status'] = 'error'
            jobj['error_msg'] = e.__str__()
    else:
        code = 400
        jobj['status'] = 'error'
        jobj['error_msg'] = e.__str__()

    response = json.dumps(jobj, indent=2)
    logger.debug('response for %s:%s' % (handle_function.__str__(), response))
    write_response(request_handler, code, response)


# ================================ tests ========================================

def test_get_handler(request_handler):
    request_handler.send_response(500)
    request_handler.end_headers()


# test server stop when delay in handlers
def test_get_handler2(request_handler):
    request_handler.send_response(200)
    request_handler.send_header('Content-Length', 100)
    request_handler.end_headers()
    logger.info('begin sleep')
    while not request_handler.server.stopflag:
        logger.info('sleep')
        time.sleep(1)
    logger.info('end sleep')


def test():
    server = httpserver()
    server.register_get('/path_registered', test_get_handler)
    server.register_get('/path_registered2', test_get_handler2)
    server.start('127.0.0.1', 9000)

    try:
        urllib2.urlopen('http://127.0.0.1:9000/path_unregistered')
    except Exception, e:
        logger.info(e.__str__())

    try:
        urllib2.urlopen('http://127.0.0.1:9000/path_registered')
    except Exception, e:
        logger.info(e.__str__())

    try:
        urllib2.urlopen('http://127.0.0.1:9000/path_registered?a=1')
    except Exception, e:
        logger.info(e.__str__())

    try:
        logger.info('%s', urllib2.urlopen('http://127.0.0.1:9000/path_registered2'))
        time.sleep(3)
        logger.info('begin stop')
        server.stop()
        logger.info('end stop')
    except Exception, e:
        logger.info(e.__str__())


if __name__ == '__main__':
    test()
