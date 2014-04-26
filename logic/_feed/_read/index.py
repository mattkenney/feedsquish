#
# Copyright 2012, 2014 Matt Kenney
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

import datetime
import threading
import urllib
import urllib2

import webob

import feeds
import filters

def action(context):
    user = context['user']
    subid = context['path_parameters'].get('feed')
    artid = context['path_parameters'].get('read')
    articleUrl = filters.decode_segment(artid[4:])
    sub = feeds.redis.hgetall(subid)
    art = feeds.redis.hgetall(artid)
    if not art:
        return context['request'].get_response(webob.exc.HTTPNotFound())
    art['subid'] = subid
    art['artid'] = artid
    art['feedName'] = sub['feedName'] if sub else ''
    art['articleDate'] = str(datetime.datetime.utcfromtimestamp(float(art['date'])))
    art['articleUrl'] = articleUrl
    articleGuid = art.get('guid') if art else None
    context['content'] = feeds.get_article_content(articleUrl, articleGuid, sub, [])
    context['article'] = feeds.makeUnicode(art)

    # prefetch the next article
    if not context['parameters'].get('prefetch'):
        params = dict()
        params['feed'] = context['parameters'].get('feed', '')
        params['show'] = context['parameters'].get('show', '')
        params['date'] = art['date']
        params['skip::'] = 1
        params['prefetch'] = 1
        cookie = context['request'].headers.get('Cookie', '')
        fetch = threading.Thread(target=prefetch, args=(params, cookie))
        fetch.daemon = True
        fetch.start()

def prefetch(params, cookie):
    req = urllib2.Request('http://localhost:8080/', urllib.urlencode(params), { 'Cookie':cookie })
    urllib2.urlopen(req)
