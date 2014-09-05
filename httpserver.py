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
import hashlib
import Cookie
import copy

import log
logger = log.get_logger('httpserver')


class access_handler():
    INFO_PATH = '/login_needed.html'
    STEP1_PATH = '/login_token'
    STEP2_PATH = '/do_login'

    LOGIN_TIMEOUT = 1
    TIMEOUT = 15 * 60

    def __init__(self):
        self._users = dict()
# TODO: 添加blocked ip和user ??????
#         self._blocked_ip = set()
#         self._blocked_user = set()
        self._processing = dict()
        self._sessions = dict()

        self._path_exclude = set()
        self.add_path_exclude(access_handler.INFO_PATH)
        self.add_path_exclude(access_handler.STEP1_PATH)
        self.add_path_exclude(access_handler.STEP2_PATH)

    def register2httpserver(self, httpserver):
        httpserver.register_get(access_handler.INFO_PATH, self._handler_infopage)
        httpserver.register_get(access_handler.STEP1_PATH, self._handler_step1)
        httpserver.register_post(access_handler.STEP2_PATH, self._handler_step2)
        httpserver.set_access_handler(self)

    def ungister2httpserver(self, httpserver):
        httpserver.unregister_get(access_handler.INFO_PATH)
        httpserver.unregister_post(access_handler.STEP1_PATH)
        httpserver.unregister_post(access_handler.STEP2_PATH)

    def add_user(self, username, key):
        self._users[username] = key

    def del_user(self, username):
        del self._users[username]

    def add_path_exclude(self, path):
        if path not in self._path_exclude:
            self._path_exclude.add(path)

    def del_path_exclude(self, path):
        self._path_exclude.remove(path)

    def check_access(self, path, request_handler):
        if path in self._path_exclude:
            return True

        if 'Cookie' not in request_handler.headers:
            logger.debug('no cookie found, send need login')
            self._send_needlogin(request_handler)
            return False

        c = Cookie.SimpleCookie(request_handler.headers["Cookie"])
        if c['token'].value not in self._sessions:
            logger.debug('token (%s) not found, send FAILED!' % c['token'])
            self._send_needlogin(request_handler)
            return False

        session = self._sessions[c['token'].value]

        if session['ip'] != request_handler.client_address[0]:
            logger.debug('ip changed, login:%s, curr:%s' % (session['ip'], request_handler.client_address[0]))
            self._send_needlogin(request_handler)
            return False

        timecurr = time.time()
        if abs(session['active_time'] - timecurr) > access_handler.TIMEOUT:
            logger.debug('timeout, last active:%d, curr:%d' % (session['active_time'], timecurr))
            self._sessions.remove(session)
            self._send_needlogin(request_handler)
            return False
        session['active_time'] = timecurr

        return True

    def _handler_infopage(self, request_handler):
        msg = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html><head><title>Login needed</title></head><body><p>You should first login</p></body></html>'''
        write_response(request_handler, 200, msg)

    def _handler_step1(self, request_handler):
        client_ip = request_handler.client_address[0]
        timestr = time.strftime('%Y%m%d%H%M%S')
        server_random = client_ip + ':' + timestr

        # clean time and count items with same ip
        processing_count = 0
        timecurr = time.time()
        for (key, value) in self._processing.iteritems():
            if abs(timecurr - value['login_time']) > access_handler.LOGIN_TIMEOUT:
                logger.debug('clean timeout login:%s, %s' % (key, value.__str__()))
                del self._processing[key]
            if value['ip'] == client_ip:
                processing_count += 1

        if processing_count > 10:
            # TODO: send another page?
            self._send_needlogin(request_handler)
            return

        data = dict()
        data['seed'] = server_random
        data['version'] = '1.0'
        response = json.dumps(data, indent=2)
        logger.debug('response:%s' % response)

        cookie = hashlib.md5(server_random).hexdigest()
        c = Cookie.SimpleCookie()
        c['token'] = cookie
        logger.debug('token:%s' % cookie)

        procinfo = dict()
        procinfo['ip'] = request_handler.client_address[0]
        procinfo['login_time'] = time.time()
        self._processing[cookie] = procinfo

        request_handler.send_response(200)
        request_handler.send_header('Set-Cookie', c.output(header=''))
        request_handler.end_headers()
        request_handler.wfile.write(response)

    def _handler_step2(self, request_handler):
        if 'Cookie' not in request_handler.headers:
            logger.debug('no cookie found, send FAILED!')
            return self._send_failed(request_handler)
        c = Cookie.SimpleCookie(request_handler.headers["Cookie"])
        cookie = c['token'].value
        logger.debug('token:%s' % cookie)

        if cookie not in self._processing:
            logger.debug('cookie not found!')
            self._send_failed(request_handler)
        procinfo = self._processing[cookie]

        result, msg = read_post(request_handler)
        if not result:
            logger.debug('no post data, send FAILED!')
            self._send_failed(request_handler)

        try:
            request = json.loads(msg)
            logger.debug('request:%s' % (json.dumps(request, indent=2),))

            if procinfo['ip'] != request_handler.client_address[0]:
                self._send_failed(request_handler)
                return False

            timecurr = time.time()
            if abs(timecurr - procinfo['login_time']) > access_handler.LOGIN_TIMEOUT:
                self._send_failed(request_handler)
                return False

            key = hashlib.md5(self._users[request['username']] + ':' + request['seed']).hexdigest()
            logger.debug('username:%s, password:%s, key:%s' % (request['username'], self._users[request['username']], key))
            if key != request['key']:
                logger.debug('key error: (%s:%s) %s, send FAILED!' % (request['username'], request['key'], key))
                self._send_failed(request_handler)

            # clean timeout sessions
            login_count = 0
            for (key, value) in self._sessions.iteritems():
                if abs(timecurr - value['active_time']) > access_handler.TIMEOUT:
                    logger.debug('clean session: %s, %s' % (key, value.__str__()))
                    self._sessions.remove(key)
            # check user's login count
            for (key, value) in self._sessions.iteritems():
                if value['user']['username'] == request['username']:
                    login_count += 1
            if login_count > 10:
                logger.error('too many login')
                self._send_failed(request_handler)
                return

            session = copy.deepcopy(procinfo)
            del self._processing[cookie]
            session['user'] = {'username': request['username'], 'password': self._users[request['username']]}
            session['active_time'] = time.time()
            self._sessions[cookie] = session

            response = dict()
            response['status'] = 'ok'
            logger.debug('response:%s' % json.dumps(response, indent=2))
            write_response(request_handler, 200, json.dumps(response, indent=2))
        except (IOError, ValueError):
            logger.exception('got exception:')
            self._send_failed(request_handler)

    def _send_failed(self, request_handler):
            response = dict()
            response['status'] = 'error'
            write_response(request_handler, 200, json.dumps(response, indent=2))

    def _send_needlogin(self, request_handler):
        request_handler.send_response(302)
        request_handler.send_header('Location', access_handler.INFO_PATH)
        request_handler.end_headers()


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
        if self.server.access_handler is not None:
            if not self.server.access_handler.check_access(parsed_path.path, self):
                return
        self.server.handlers_get[parsed_path.path](self)

    def do_POST(self):
        parsed_path = urlparse.urlparse(self.path)
        if self.server.handlers_post is None or parsed_path.path not in self.server.handlers_post:
            self.send_response(404)
            self.end_headers()
            return
        if self.server.access_handler is not None:
            if not self.server.access_handler.check_access(parsed_path.path, self):
                return
        self.server.handlers_post[parsed_path.path](self)


class _threaded_httpserver(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):

    # force stop handler threads on server thread exit
    daemon_threads = True

    allow_reuse_address = True

    def set_handlers(self, handlers_get, handlers_post):
        self.handlers_get = handlers_get
        self.handlers_post = handlers_post

    def set_access_handler(self, access_handler):
        self.access_handler = access_handler

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
        self._access_handler = None

    def start(self, host, port):
        logger.info('host:%s, port:%d, status:%d' % (host, port, self._status))
        if self._status != 0:
            logger.error('invalid status:%d' % self._status)
            return
        self._server = _threaded_httpserver((host, port), _request_handler)
        self._server.set_handlers(self._handlers_get, self._handlers_post)
        self._server.set_access_handler(self._access_handler)
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

    def set_access_handler(self, access_handler):
        self._access_handler = access_handler


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
    code = 200
    jobj = dict()
    if request_handler.command == 'POST':
        result, msg = read_post(request_handler)
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
            jobj['error_msg'] = 'read_post FAILED!'
    elif request_handler.command == 'GET':
        try:
            jobj = handle_function(None)
        except Exception, e:
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
