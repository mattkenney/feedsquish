#!/usr/bin/env python
#
# Copyright 2012 Matt Kenney
#
# This file is part of Feedsquish.
#
# Feedsquish is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# Feedsquish is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Feedsquish.  If not, see <http://www.gnu.org/licenses/>.
#

import cgi
import string

import redis.client
import passlib.context
import webob
import webob.exc

import filters

ctx = passlib.context.CryptContext(schemes=['pbkdf2_sha1', 'pbkdf2_sha512'])

_form_login = string.Template("""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8" />
<meta content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" name="viewport" />
<link href="/css/default.css" rel="stylesheet" type="text/css" />
<title>Sign In</title>
</head>
<body class="idem-body">
<form action="$action" method="post">
<div class="idem-message">$message</div>
<table class="idem-table">
<tr>
<td><label for="username">Username:</label></td>
<td><input id="username" name="idem.username" type="text" value="$username" /></td>
</tr>
<tr>
<td><label for="password">Password:</label></td>
<td><input id="password" name="idem.password" type="password" value="$password" /></td>
</tr>
<tr>
<td></td>
<td><input type="submit" value="Sign In" /></td>
</tr>
</table>
</form>
<form action="$action" method="post">
<div class="idem-switch">
<input name="idem.create" type="submit" value="Create an New Account" />
</div>
</form>
</body>
</html>
""")

_form_create = string.Template("""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8" />
<meta content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" name="viewport" />
<title>Create Account</title>
<link href="/css/default.css" rel="stylesheet" type="text/css" />
</head>
<body class="idem-body">
<form action="$action" method="post">
<input name="idem.create" type="hidden" value="" />
<div class="idem-message">$message</div>
<table class="idem-table">
<tr>
<td><label for="username">Username:</label></td>
<td><input id="username" name="idem.username" type="text" value="$username" /></td>
</tr>
<tr>
<td><label for="password1">Password:</label></td>
<td><input id="password1" name="idem.password1" type="password" value="$password1" /></td>
</tr>
<tr>
<td><label for="password2">Retype password:</label></td>
<td><input id="password2" name="idem.password2" type="password" value="$password2" /></td>
</tr>
<tr>
<td colspan="2">
<p>By clicking Create Account, you agree<br />
to our <a href="/policies/termsofuse.html" target="_blank">Terms of Use</a> and
<a href="/policies/privacy.html" target="_blank">Privacy Policy</a>.</p>
</td>
</tr>
<tr>
<td></td>
<td><input type="submit" value="Create Account" /></td>
</tr>
</table>
</form>
</form>
<form action="$action">
<div class="idem-switch">
<input type="submit" value="Sign In with Existing Account" />
</div>
</form>
</body>
</html>
""")

_form_change = string.Template("""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8" />
<meta content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0" name="viewport" />
<title>Change Password</title>
<link href="/css/default.css" rel="stylesheet" type="text/css" />
</head>
<body class="idem-body">
<form action="$action" method="post">
<input name="idem.change" type="hidden" value="" />
<div class="idem-message">$message</div>
<table class="idem-table">
<tr>
<td><label for="password">Current password:</label></td>
<td><input id="password" name="idem.password" type="password" value="$password" /></td>
</tr>
<tr>
<td><label for="password1">New password:</label></td>
<td><input id="password1" name="idem.password1" type="password" value="$password1" /></td>
</tr>
<tr>
<td><label for="password2">Retype new password:</label></td>
<td><input id="password2" name="idem.password2" type="password" value="$password2" /></td>
</tr>
<tr>
<td></td>
<td><input type="submit" value="Change Password" /></td>
</tr>
</table>
</form>
</body>
</html>
""")

class Authenticator(object):
    def __init__(self, application, config={}):
        self.application = application
        self.session_key = config.get("idem.session.key", "session")
        self.user_key = config.get("idem.user.key", "REMOTE_USER")
        self.redis = redis.client.StrictRedis()
        self.dummy = ctx.encrypt("password")
        self.auth_change_password = config.get("idem.auth_change_password", "/auth_change_password")
        self.auth_logout = config.get("idem.auth_logout", "/auth_logout")

    def _change_password(self, environ, start_response):
        request = webob.Request(environ)
        action = request.headers.get('X-Forwarded-Path', request.path)
        message = ""
        userid = environ["REMOTE_USER"]
        password = request.params.get("idem.password", "")
        password1 = request.params.get("idem.password1", "")
        password2 = request.params.get("idem.password2", "")
        if request.method != "POST":
            pass
        elif len(password1) < 6:
            message = "Passwords must be at least 6 letters."
        elif password1 != password2:
            message = "Passwords do not match."
        else:
            passwd = self.redis.hget(userid, "password")
            if passwd:
                if ctx.verify(password, passwd):
                    self.redis.hset(userid, "password", ctx.encrypt(password1))
                    response = request.get_response(webob.exc.HTTPFound(location="/"))
                    return response(environ, start_response)
            else:
                ctx.verify(password, self.dummy)
            message = "The current password you entered is incorrect."
        response = webob.Response()
        response.charset = "UTF-8"
        response.text = unicode(_form_change.substitute(
            action=cgi.escape(action, True),
            message=cgi.escape(message, True),
            password=cgi.escape(password, True),
            password1=cgi.escape(password1, True),
            password2=cgi.escape(password2, True)
        ))
        return response(environ, start_response)

    def _create_user(self, environ, start_response, request, session):
        action = request.headers.get('X-Forwarded-Path', request.path)
        username = request.params.get("idem.username", "")
        password1 = request.params.get("idem.password1", "")
        password2 = request.params.get("idem.password2", "")
        message = ""
        if request.params["idem.create"] != "":
            pass # show blank form
        elif len(username) < 4:
            message = "Usernames must be at least 4 letters."
        elif len(password1) < 6:
            message = "Passwords must be at least 6 letters."
        elif password1 != password2:
            message = "Passwords do not match."
        else:
            userid = "user/" + filters.encode_segment(username)
            if self.redis.hsetnx(userid, "password", ctx.encrypt(password1)):
                session[self.user_key] = userid
                response = request.get_response(webob.exc.HTTPFound(location=action))
                return response(environ, start_response)
            message = "Username already exists."
        response = webob.Response()
        response.charset = "UTF-8"
        response.text = unicode(_form_create.substitute(
            action=cgi.escape(action, True),
            message=cgi.escape(message, True),
            username=cgi.escape(username, True),
            password1=cgi.escape(password1, True),
            password2=cgi.escape(password2, True)
        ))
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        message = ""
        session = environ.get(self.session_key)
        userid = session.get(self.user_key)
        if environ["PATH_INFO"] == self.auth_logout:
            session[self.user_key] = None
            message = "You have signed out."
        elif userid:
            environ["REMOTE_USER"] = userid
            if environ["PATH_INFO"] == self.auth_change_password:
                return self._change_password(environ, start_response)
            else:
                return self.application(environ, start_response)
        request = webob.Request(environ)
        action = request.headers.get('X-Forwarded-Path', request.path)
        username = request.params.get("idem.username", "")
        password = request.params.get("idem.password", "")
        if action == environ["PATH_INFO"] == self.auth_logout:
            action = "/"
        if request.method == "POST":
            if request.params.has_key("idem.create"):
                return self._create_user(environ, start_response, request, session)
            else:
                userid = "user/" + filters.encode_segment(username)
                passwd = self.redis.hget(userid, "password")
                if passwd:
                    if ctx.verify(password, passwd):
                        session[self.user_key] = userid
                        response = request.get_response(webob.exc.HTTPFound(location=action))
                        return response(environ, start_response)
                else:
                    ctx.verify(password, self.dummy)
                message = "The username or password you entered is incorrect."
        response = webob.Response()
        response.charset = "UTF-8"
        response.text = unicode(_form_login.substitute(
            action=cgi.escape(action, True),
            message=cgi.escape(message, True),
            username=cgi.escape(username, True),
            password=cgi.escape(password, True)
        ))
        return response(environ, start_response)
