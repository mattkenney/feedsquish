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

import datetime

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
    context['content'] = feeds.get_article_content(articleUrl, articleGuid, sub)
    context['article'] = feeds.makeUnicode(art)

#    # prefetch the next article
#    if stat:
#        params = dict()
#        params['user'] = user.email()
#        params['date'] = stat.articleDate.isoformat()
#        feedFilter = context['rupta_request'].params.get('feed')
#        if feedFilter:
#            params['feed'] = feedFilter
#        if context['rupta_request'].params.get('show') == 'all':
#            params['show'] = 'all'
#        taskqueue.add(url='/admin/prefetch.html', params=params)

