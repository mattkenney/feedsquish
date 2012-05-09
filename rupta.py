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

import mimetypes
import os
import re
import traceback

import jinja2
import webob

import filters

templates = os.path.join(os.path.dirname(__file__), 'templates')
static = os.path.join(os.path.dirname(__file__), 'static')
env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates))
has_charset = re.compile('''((^text/)|(/ecmascript$)|(/(x-)?javascript$)|((/|\+)xml$))''')

for key in dir(filters):
    attribute = getattr(filters, key)
    if callable(attribute):
        env.filters[key] = attribute

def application(environ, start_response):
    request = webob.Request(environ)

    # virtual path segments
    virtual_segments = [x for x in request.path.split('/') if x]
    if request.path.endswith('/'):
        virtual_segments.append('index.html')

    # serve static files for specific path prefixes
    if len(virtual_segments) > 0 and virtual_segments[0] in [ 'css', 'favicon.ico', 'images', 'js' ]:
        path = os.path.join(static, *virtual_segments)
        # set the content-type header based on the file extension
        (content_type, encoding) = mimetypes.guess_type(path)
        content_type = content_type if content_type else 'text/html'
        if has_charset.match(content_type):
            content_type = content_type + '; charset=UTF-8';
        f = open(path, 'rb')
        body = f.read()
        f.close()
        # build response
        response = webob.Response()
        response.headers['Content-Type'] = content_type
        response.headers['Content-Length'] = len(body)
        response.body = body
        return response(environ, start_response)

    # map virtual path to physical path and parameters
    physical_segments = []
    path_parameters = {}
    path_translated = None
    index = 1
    last = len(virtual_segments) - 1
    while True:
        if index < last:
            path_parameters[virtual_segments[index - 1]] = filters.decode_segment(virtual_segments[index])
            physical_segments.append('_' + virtual_segments[index - 1])
        else:
            physical_segments.append(virtual_segments[index - 1])
            if index == last:
                physical_segments.append(virtual_segments[index])
                path_translated = os.path.join(templates, *physical_segments)
                if not os.path.isfile(path_translated):
                    path_parameters[virtual_segments[index - 1]] = filters.decode_segment(virtual_segments[index])
                    physical_segments.pop()
                    physical_segments.pop()
                    physical_segments.append('_' + virtual_segments[index - 1])
            break
        index = index + 2
    if not path_translated:
        path_translated = os.path.join(templates, *physical_segments)

    # see if we need a url path prefix
    root = ''
    if 'X-Forwarded-Path' in request.headers:
        path = request.headers['X-Forwarded-Path']
        if path.endswith(request.path):
            root = path[0:-len(request.path)]

    if not request.path.endswith('/') and os.path.isdir(path_translated):
        # send redirect with the slash
        response = request.get_response(webob.exc.HTTPFound(location=root + request.path + '/'))
        return response(environ, start_response)

    # page relative base template paths
    depth = len(physical_segments)
    base = [ '/'.join(physical_segments[0:i-1]) + '/_base.html' for i in range(0, depth) ]
    base[0:2] = [ '_baseroot.html', '_baseroot.html' ]

    # see if an action module exists for the page
    module = None
    action_segments = physical_segments[:]
    action_segments.insert(0, 'logic')
    (action_segments[-1], tmp) = os.path.splitext(action_segments[-1])
    action_path = os.path.join(os.path.dirname(__file__), *action_segments) + '.py'
    if os.path.exists(action_path):
        module = __import__('.'.join(action_segments))
        for segment in action_segments[1:]:
            module = getattr(module, segment)

    context = {}
    context['request'] = request
    context['root'] = root
    context['parameters'] = dict( [ ( name, value ) for name, value in request.params.items() ] )
    context['base'] = base
    context['virtual_segments'] = virtual_segments
    context['action_path'] = action_path
    context['path_parameters'] = path_parameters
    context['user'] = environ["REMOTE_USER"]
    context['WSGI'] = environ
    environ['PATH_TRANSLATED'] = path_translated

    # call the action method in the action module if it exists
    response = module.action(context) if module else None
    if response:
        # if the action returns something, then it does not need its template to be rendered
        return response(environ, start_response)
    elif os.path.exists(path_translated):
        # set the content-type header based on the file extension
        (content_type, encoding) = mimetypes.guess_type(path_translated)
        content_type = content_type if content_type else 'text/html'
        if has_charset.match(content_type):
            content_type = content_type + '; charset=UTF-8';
        response = webob.Response()
        environ['rupta_response'] = response
        response.headers['Content-Type'] = content_type
        # render the page
        path = os.path.relpath(path_translated, templates)
        template = env.get_template(path)
        try:
            response.text = template.render(context)
        except Exception:
            context['exception'] = traceback.format_exc();
            print context['exception']
            response = request.get_response(webob.exc.HTTPInternalServerError())
    else:
        response = request.get_response(webob.exc.HTTPNotFound())

    return response(environ, start_response)

#def sendError(request, response, context, status):
#    context['status_code'] = status
#    context['status_message'] = webapp.Response.http_status_message(status)
#    response.headers['Content-Type'] = 'text/html; charset=UTF-8'
#    template = env.get_template('error.html')
#    response.text = template.render(context)

