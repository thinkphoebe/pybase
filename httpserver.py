# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 1, 2014
'''
import copy
import hashlib
import http.cookies
import http.server
import json
import random
import socketserver
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.parse
import urllib.request

from . import log

logger = log.get_logger('httpserver')


class access_handler():
    INFO_PATH = '/login_required.html'
    LOGIN_PATH = '/login'
    LOGOUT_PATH = '/logout'

    LOGIN_TIMEOUT = 10
    TIMEOUT = 10 * 60

    def __init__(self):
        self._users = dict()
        self._processing = dict()
        self._sessions = dict()

        self._path_exclude = set()
        self.add_path_exclude(access_handler.INFO_PATH)
        self.add_path_exclude(access_handler.LOGIN_PATH)

    def register2httpserver(self, httpserver):
        httpserver.register_get(access_handler.INFO_PATH, self._handler_infopage)
        httpserver.register_get(access_handler.LOGIN_PATH, self._handler_login)
        httpserver.register_post(access_handler.LOGIN_PATH, self._handler_login)
        httpserver.register_get(access_handler.LOGOUT_PATH, self._handler_logout)
        httpserver.set_access_handler(self)

    def ungister2httpserver(self, httpserver):
        httpserver.unregister_get(access_handler.INFO_PATH)
        httpserver.unregister_get(access_handler.LOGIN_PATH)
        httpserver.unregister_post(access_handler.LOGIN_PATH)
        httpserver.unregister_get(access_handler.LOGOUT_PATH)

    def add_user(self, username, key):
        self._users[username] = key

    def del_user(self, username):
        del self._users[username]
        k = None
        for key, value in self._sessions.items():
            if value['user']['username'] == username:
                k = key
                break
        if k is not None:
            del self._sessions[k]

    def add_path_exclude(self, path):
        if path not in self._path_exclude:
            self._path_exclude.add(path)

    def del_path_exclude(self, path):
        self._path_exclude.remove(path)

    def _check_setcookie(self, request_handler):
        set_cookie = True
        if 'Cookie' in request_handler.headers:
            c = http.cookies.SimpleCookie(request_handler.headers['Cookie'])
            if 'token' in c and c['token'].value in self._processing and \
                    time.time() - self._processing[c['token'].value]['token_time'] < access_handler.LOGIN_TIMEOUT:
                set_cookie = False
        if set_cookie:
            token = self._get_token2set(request_handler)
            if token is not None:
                c = http.cookies.SimpleCookie()
                c['token'] = token
                logger.debug('token:%s' % token)
                request_handler.send_header('Set-Cookie', c.output(header=''))
        return True

    def send_needlogin(self, request_handler):
        request_handler.send_response(302)
        request_handler.send_header('Location', access_handler.INFO_PATH)
        self._check_setcookie(request_handler)
        request_handler.end_headers()

    def check_access(self, path, request_handler):
        if path in self._path_exclude:
            return True

        if 'Cookie' not in request_handler.headers:
            logger.debug('no cookie found, send need login')
            return False
        c = http.cookies.SimpleCookie(request_handler.headers['Cookie'])
        if 'token' not in c:
            logger.debug('no token in Cookie')
            return False

        if c['token'].value not in self._sessions:
            logger.debug('token (%s) not found in sessions!' % c['token'])
            return False

        session = self._sessions[c['token'].value]

        if session['ip'] != request_handler.client_address[0]:
            logger.debug('ip changed, login:%s, curr:%s' % (session['ip'], request_handler.client_address[0]))
            return False

        timecurr = time.time()
        if abs(session['active_time'] - timecurr) > access_handler.TIMEOUT:
            logger.debug('timeout, last active:%s, curr:%s' % (
            time.strftime('%Y%m%d %H:%M:%S', time.localtime(session['active_time'])), \
            time.strftime('%Y%m%d %H:%M:%S', time.localtime(timecurr))))
            del self._sessions[c['token'].value]
            return False

        session['active_time'] = timecurr
        return True

    def _get_token2set(self, request_handler):
        def _make_cookie():
            timecurr = time.time()

            processing_count = 0
            oldest = (None, None)

            for key in list(self._processing.keys()):
                value = self._processing[key]
                # clean timeout
                if abs(timecurr - value['token_time']) > access_handler.LOGIN_TIMEOUT:
                    logger.debug('clean timeout login:%s, %s' % (key, value.__str__()))
                    del self._processing[key]

                if value['ip'] == request_handler.client_address[0]:
                    if oldest[0] is None or value['token_time'] < oldest[0]:
                        oldest = (value['token_time'], key)
                    processing_count += 1
            # delete oldest items from same IP
            if processing_count > 10:
                logger.warning('too many in processing, delete oldest:%s' % oldest[2])
                del self._processing[oldest[2]]

            procinfo = dict()
            server_random = request_handler.client_address[0] + ':' + time.strftime('%Y%m%d%H%M%S',
                    time.localtime(timecurr)) + ':' + str( random.randint(0, 100000000))
                    time.localtime(timecurr)) + ':' + str(random.randint(0, 100000000))
            token = hashlib.md5(server_random).hexdigest()
            procinfo['ip'] = request_handler.client_address[0]
            procinfo['token_time'] = timecurr
            self._processing[token] = procinfo
            logger.debug('make token [%s] for client [%s]' % (token, request_handler.client_address[0]))
            return token

        if 'Cookie' not in request_handler.headers:
            return _make_cookie()
        c = http.cookies.SimpleCookie(request_handler.headers["Cookie"])
        if 'token' not in c:
            return _make_cookie()
        if c['token'].value not in self._processing:
            return _make_cookie()
        data = self._processing[c['token'].value]

        if data['ip'] != request_handler.client_address[0]:
            logger.debug('ip changed, login:%s, curr:%s' % (data['ip'], request_handler.client_address[0]))
            del self._processing[c['token'].value]
            return _make_cookie()

        timecurr = time.time()
        if abs(data['token_time'] - timecurr) > access_handler.LOGIN_TIMEOUT:
            logger.debug('timeout, last token_time:%s, curr:%s' % (
            time.strftime('%Y%m%d %H:%M:%S', time.localtime(data['token_time'])), \
            time.strftime('%Y%m%d %H:%M:%S', time.localtime(timecurr))))
            del self._processing[c['token'].value]
            return _make_cookie()

        return None

    def _send_failed(self, request_handler, msg):
        request_handler.send_response(200)
        self._check_setcookie(request_handler)
        request_handler.end_headers()

        response = dict()
        response['status'] = 'error'
        response['error_msg'] = msg
        request_handler.wfile.write(json.dumps(response, indent=2))

    def _handler_infopage(self, request_handler):
        msg = '''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html><head><title>Login needed</title></head><body><p>You should first login</p></body></html>'''

        request_handler.send_response(200)
        if not self.check_access(None, request_handler):
            self._check_setcookie(request_handler)
        request_handler.end_headers()
        request_handler.wfile.write(msg)

    def _handler_login(self, request_handler):
        if 'Cookie' not in request_handler.headers:
            logger.debug('no cookie found, send FAILED!')
            self._send_failed(request_handler, 'need cookie')
            return
        c = http.cookies.SimpleCookie(request_handler.headers["Cookie"])
        if 'token' not in c:
            logger.debug('no token found in cookie, send FAILED!')
            self._send_failed(request_handler, 'need token')
            return
        token = c['token'].value
        logger.debug('token:%s' % token)

        if token in self._sessions:
            logger.info('already login')
            write_response(request_handler, 200, json.dumps({'status': 'ok'}, indent=2))
            return

        if token not in self._processing:
            logger.debug('invalid token')
            self._send_failed(request_handler, 'invalid token')
            return
        procinfo = self._processing[token]

        result, msg = read_post(request_handler)
        if not result:
            logger.debug('no post data, send FAILED!')
            self._send_failed(request_handler, 'need key')
            return

        try:
            request = json.loads(msg)
            logger.debug('request:%s' % (json.dumps(request, indent=2),))

            if procinfo['ip'] != request_handler.client_address[0]:
                self._send_failed(request_handler, 'IP changed')
                return

            timecurr = time.time()
            if abs(timecurr - procinfo['token_time']) > access_handler.LOGIN_TIMEOUT:
                self._send_failed(request_handler, 'timeout')
                return

            if 'username' not in request or 'seed' not in request or 'key' not in request:
                self._send_failed(request_handler, 'invalid data')
                return

            if len(request['username']) == 0:
                self._send_failed(request_handler, 'login required')
                return

            if request['username'] not in self._users:
                self._send_failed(request_handler, 'user not found')
                return

            key_tmp = hashlib.md5(self._users[request['username']] + ':' + request['seed']).hexdigest()
            key = hashlib.md5(key_tmp + ':' + token).hexdigest()
            logger.debug('username:%s, password:%s, key:%s' % (request['username'], self._users[request['username']], key))
            if key != request['key']:
                logger.debug('key error: (%s:%s) %s, send FAILED!' % (request['username'], request['key'], key))
                self._send_failed(request_handler, 'password error')
                return

            # clean timeout sessions
            login_count = 0
            for key in list(self._sessions.keys()):
                value = self._sessions[key]
                if abs(timecurr - value['active_time']) > access_handler.TIMEOUT:
                    logger.debug('clean session: %s, %s' % (key, value.__str__()))
                    del self._sessions[key]
            # check user's login count
            for (key, value) in self._sessions.items():
                if value['user']['username'] == request['username']:
                    login_count += 1
            if login_count > 10:
                logger.error('too many login')
                self._send_failed(request_handler, 'too many login')
                return

            session = copy.deepcopy(procinfo)
            del self._processing[token]
            session['user'] = {'username': request['username'], 'password': self._users[request['username']]}
            session['login_time'] = time.time()
            session['active_time'] = time.time()
            self._sessions[token] = session

            response = dict()
            response['status'] = 'ok'
            logger.debug('response:%s' % json.dumps(response, indent=2))
            write_response(request_handler, 200, json.dumps(response, indent=2))
        except (IOError, ValueError, KeyError):
            logger.exception('got exception:')
            self._send_failed(request_handler, 'server error')

    def _handler_logout(self, request_handler):
        if 'Cookie' not in request_handler.headers:
            write_response(request_handler, 200, '{"status": "error", "error_msg": "no cookie found"}')
            logger.debug('no cookie found')
            return
        c = http.cookies.SimpleCookie(request_handler.headers["Cookie"])
        if 'token' not in c:
            write_response(request_handler, 200, '{"status": "error", "error_msg": "no token in Cookie"}')
            logger.debug('no token in Cookie')
            return
        if c['token'].value not in self._sessions:
            logger.debug('token (%s) not found in sessions!' % c['token'])
            write_response(request_handler, 200, '{"status": "error", "error_msg": "token not found in sessions"}')
            return
        session = self._sessions[c['token'].value]
        logger.debug('logout, ip:%s, login time:%s' % (
        session['ip'], time.strftime('%Y%m%d %H:%M:%S', time.localtime(session['login_time']))))
        del self._sessions[c['token'].value]
        write_response(request_handler, 200, '{"status": "ok"}')


class _request_handler(http.server.BaseHTTPRequestHandler):
    # redirect log message to logger
    def log_message(self, args, *vargs):
        logger.info("HTTPSERVER - %s", args % vargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if self.server.handlers_get is None or parsed_path.path not in self.server.handlers_get:
            self.send_response(404)
            self.end_headers()
            return
        if self.server.access_handler is not None:
            if not self.server.access_handler.check_access(parsed_path.path, self):
                self.server.access_handler.send_needlogin(self)
                return
        self.server.handlers_get[parsed_path.path](self)

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if self.server.handlers_post is None or parsed_path.path not in self.server.handlers_post:
            self.send_response(404)
            self.end_headers()
            return
        if self.server.access_handler is not None:
            if not self.server.access_handler.check_access(parsed_path.path, self):
                # ATTENTION: 不读取post数据会导致客户端产生'[Errno 32] Broken pipe'的错误
                # 客户端应避免在未登录前post大块数据
                read_post(self)
                self.server.access_handler.send_needlogin(self)
                return
        self.server.handlers_post[parsed_path.path](self)


class _threaded_httpserver(socketserver.ThreadingMixIn, http.server.HTTPServer):
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
        self._serve_thrd.setName('http_handler')
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
            urllib.request.urlopen('http://%s:%s' % (host, port))
        except IOError:
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
            logger.warning('"%s" already registered by %s' % (path, self._handlers_get[path]).__str__())
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
            logger.warning('"%s" already registered by %s' % (path, self._handlers_post[path]).__str__())
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

    def get_session_info(self, token):
        if token in self._access_handler._sessions:
            return self._access_handler._sessions[token]
        return None


# ================================ some utility functions  ========================================

def read_post(request_handler):
    try:
        return (True, request_handler.rfile.read(int(request_handler.headers['content-length'])))
    except IOError:
        logger.exception('got exception:')
        return (False, traceback.format_exc())


def write_response(request_handler, code=200, msg='', debug=False):
    try:
        request_handler.send_response(code)
        request_handler.send_header('Content-Length', len(msg))
        request_handler.end_headers()
        request_handler.wfile.write(msg)
        if debug:
            logger.debug('code:%d, msg:%s' % (code, msg))
        return True
    except IOError:
        logger.exception('got exception:')
        return False


def handle_json_post(request_handler, handle_function):
    jobj = dict()
    if request_handler.command == 'POST':
        result, msg = read_post(request_handler)
        if result:
            try:
                request = json.loads(msg)
                logger.debug('request for %s:%s' % (handle_function.__str__(), json.dumps(request, indent=2)))
                jobj = handle_function(request)
            except (IOError, ValueError, KeyError, TypeError):
                jobj['status'] = 'error'
                jobj['error_msg'] = traceback.format_exc()
        else:
            jobj['status'] = 'error'
            jobj['error_msg'] = 'read_post FAILED!'
    elif request_handler.command == 'GET':
        try:
            jobj = handle_function(None)
        except Exception as e:
            jobj['status'] = 'error'
            jobj['error_msg'] = traceback.format_exc()

    response = json.dumps(jobj, indent=2)
    logger.debug('response for %s:%s' % (handle_function.__str__(), response))
    write_response(request_handler, 200, response)


def client_str(request_handler):
    ip = request_handler.client_address[0]
    token = 'none'
    if 'Cookie' in request_handler.headers:
        c = http.cookies.SimpleCookie(request_handler.headers["Cookie"])
        if 'token' in c:
            token = c['token'].value
    return '[ip:%s, token:%s]' % (ip, token)


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
        urllib.request.urlopen('http://127.0.0.1:9000/path_unregistered')
    except Exception as e:
        logger.exception('got exception:')

    try:
        urllib.request.urlopen('http://127.0.0.1:9000/path_registered')
    except Exception as e:
        logger.exception('got exception:')

    try:
        urllib.request.urlopen('http://127.0.0.1:9000/path_registered?a=1')
    except Exception as e:
        logger.exception('got exception:')

    try:
        logger.info('%s', urllib.request.urlopen('http://127.0.0.1:9000/path_registered2'))
        time.sleep(3)
        logger.info('begin stop')
        server.stop()
        logger.info('end stop')
    except Exception as e:
        logger.exception('got exception:')


if __name__ == '__main__':
    test()
