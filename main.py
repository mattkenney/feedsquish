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

import beaker.middleware

import idem
import rupta

config = {
    "idem.session.key": "beaker.session",
    "session.auto": True,
    "session.cookie_expires": 2592000,
    "session.key": "session",
    "session.secret": "b9f8649e-a29b-41b5-a9ed-1f30491a53c1",
    "session.type": "cookie",
    "session.validate_key": "8bc2959c-4fdd-4e2e-a89f-eedc2cdc5003"
}

app = rupta.application

app = idem.Authenticator(app, config)

app = beaker.middleware.SessionMiddleware(app, config)

if __name__ == '__main__':
    import cherrypy.wsgiserver
    server = cherrypy.wsgiserver.CherryPyWSGIServer(('0.0.0.0', 8080), app)
    server.start()

