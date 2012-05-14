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
import time
import traceback
import urllib

import feedparser
import webob

import feeds

def action(context):
    sub = None
    lst = [] if context['parameters'].get('test') else None
    subid = context['path_parameters'].get('feed')
    if subid:
        sub = feeds.redis.hgetall(subid)
        if not sub:
            return context['request'].get_response(webob.exc.HTTPNotFound())
    location = context['parameters'].get('next')
    if not location:
        location = context['request'].headers.get('Referer')
    if not location:
        location = '../' if subid else '../feed/'
    context['next'] = location
    if context['request'].method == 'POST':
        if context['parameters'].get('cancel'):
            return context['request'].get_response(webob.exc.HTTPFound(location=location))
        if context['parameters'].get('delete'):
            if sub:
                feeds.redis.srem(context['user'] + "/subs", subid)
                feeds.redis.delete(subid)
            return context['request'].get_response(webob.exc.HTTPFound(location=location))
        feedUrl = context['parameters'].get('feedUrl')[0:1024].strip()
        feedName = context['parameters'].get('feedName')[0:16].strip()
        if not feedUrl:
            context.setdefault('errors', []).append('Url is required')
        elif not feedName:
            context.setdefault('errors', []).append('Name is required')
        else:
            sub = {}
            sub['user'] = context['user']
            sub['feedUrl'] = feedUrl
            sub['feedName'] = feedName
            sub['useGuid'] = '1' if context['parameters'].get('useGuid') else '0'
            sub['prefixRemove'] = context['parameters'].get('prefixRemove')[0:1024].strip()
            sub['prefixAdd'] = context['parameters'].get('prefixAdd')[0:1024].strip()
            sub['suffixRemove'] = context['parameters'].get('suffixRemove')[0:1024].strip()
            sub['suffixAdd'] = context['parameters'].get('suffixAdd')[0:1024].strip()
            sub['xpath'] = context['parameters'].get('xpath')[0:8096].strip()
            sub['extra'] = ','.join(context['request'].params.getall('extra'))[0:1024].strip()
            if lst is None:
                if subid:
                    feeds.redis.hmset(subid, sub)
                else:
                    subid = "sub/" + str(feeds.redis.incr("ids/sub"))
                    feeds.redis.hmset(subid, sub)
                    feeds.redis.sadd(context['user'] + "/subs", subid)
                feeds.redis.zadd("feeds", time.time(), feedUrl)
                return context['request'].get_response(webob.exc.HTTPFound(location=location))
            else:
                try:
                    lst.append('fetching and parsing ' + sub['feedUrl'] + '\n')
                    parser = feedparser.parse(sub['feedUrl'])
                    if hasattr(parser, 'status'):
                        lst.append('status ' + str(parser.status) + '\n')
                    elif hasattr(parser, 'bozo_exception'):
                        lst.append(str(parser.bozo_exception) + '\n')
                    else:
                        lst.append('feed error\n')
                    if not (hasattr(parser, 'entries') and parser.entries):
                        lst.append('feed has no entries\n')
                    else:
                        lst.append('processing sample entry...\n')
                        entry = parser.entries[0]
                        articleUrl = entry.get('link', '')
                        articleGuid = entry.get('guid', articleUrl)
                        feeds.get_article_content(articleUrl, articleGuid, sub, lst)
                except Exception, e:
                    lst.append('exception:\n')
                    lst.append(str(e))
                    lst.append('\n')
                    print traceback.format_exc()
                context['testout'] = ''.join(lst)
    if sub:
        context['parameters']['feedUrl'] = sub['feedUrl']
        context['parameters']['feedName'] = sub['feedName']
        context['parameters']['useGuid'] = 'Y' if sub['useGuid'] == '1' else ''
        context['parameters']['prefixRemove'] = sub['prefixRemove']
        context['parameters']['prefixAdd'] = sub['prefixAdd']
        context['parameters']['suffixRemove'] = sub['suffixRemove']
        context['parameters']['suffixAdd'] = sub['suffixAdd']
        context['parameters']['xpath'] = sub['xpath']

