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
import time
import urllib

import webob

import feeds
import filters

def action(context):
    feeds.update_user_maybe(context['user'])

    #LATER: if empty redirect to welcome

    action = None
    subidLast = None
    artidLast = None
    if context['request'].method == 'POST':
        for name in context['parameters'].keys():
            if name.startswith('hide:') or name.startswith('next:') or name.startswith('show:') or name.startswith('skip:'):
                parts = name.split(':')
                action = parts[0]
                subidLast = parts[1]
                artidLast = parts[2]
                break

    if action == 'hide' or action == 'next':
        scoreLast = feeds.redis.zscore(subidLast + "/unread", artidLast)
        if scoreLast:
            feeds.redis.zrem(subidLast + "/unread", artidLast)
            feeds.redis.zadd(subidLast + "/read", scoreLast, artidLast)
    elif action == 'show':
        scoreLast = feeds.redis.zscore(subidLast + "/read", artidLast)
        if scoreLast:
            feeds.redis.zrem(subidLast + "/read", artidLast)
            feeds.redis.zadd(subidLast + "/unread", scoreLast, artidLast)

    feedFilter = context['parameters'].get('feed')
    showFilter = context['parameters'].get('show')

    ids = []
    feeders = []
    now = time.time()
    cutoff = now - (60 * 24 * 60 * 60)
    for subid in feeds.redis.sort(context['user'] + "/subs", None, None, "*->feedName", None, False, True):
        feedName = feeds.redis.hget(subid, 'feedName')
        count = 0
        if feedFilter and feedFilter != subid:
            count = feeds.redis.zcard(subid + "/unread")
        else:
            before = len(ids)
            ids.extend([ (subid, feedName, artid, True, score) for artid, score in feeds.redis.zrangebyscore(subid + "/unread", "-inf", "+inf", None, None, True) ])
            count = len(ids) - before
        feeders.append({
            'subid':subid,
            'feedName': feedName,
            'counter': count
        })
        feeds.redis.zremrangebyscore(subid + "/read", "-inf", cutoff)
        if showFilter == 'all' and (feedFilter == subid or not feedFilter):
            ids.extend([ (subid, feedName, artid, False, score) for artid, score in feeds.redis.zrangebyscore(subid + "/read", "-inf", "+inf", None, None, True) ])

    # sort by date descending
    ids.sort(filters.compare, lambda x: -float(x[4]))

    qs = ''
    if feedFilter:
        qs = '?feed=' + urllib.quote_plus(feedFilter)
    if showFilter:
        qs += '&' if qs else '?'
        qs += 'show=' + urllib.quote_plus(showFilter)
    if context['parameters'].get('prefetch'):
        qs += '&' if qs else '?'
        qs += 'prefetch=1'

    if action == 'next' or action == 'skip':
        scoreLast = float(context['parameters'].get('date', 0))
        subidNext = None
        artidNext = None
        for tup in ids:
            if tup[4] <= scoreLast:
                break
            subidNext = tup[0]
            artidNext = tup[2]
        if subidNext and artidNext:
            path = context['root'] + '/feed/' + filters.encode_segment(subidNext) + '/read/' + filters.encode_segment(artidNext) + '/' + qs
            return context['request'].get_response(webob.exc.HTTPFound(location=path))

    offset = 0
    try:
        offset = int(context['parameters'].get('offset', 0))
    except:
        pass
    if offset > 0:
        context['newer'] = qs + ('&' if qs else '?') + 'offset=' + str(offset - 50)
    if len(ids) - offset > 50:
        context['older'] = qs + ('&' if qs else '?') + 'offset=' + str(offset + 50)

    articles = []
    for tup in ids[offset:offset+50]:
        art = feeds.redis.hgetall(tup[2])
        art['subid'] = tup[0]
        art['feedName'] = tup[1]
        art['artid'] = tup[2]
        art['unread'] = tup[3]
        art['articleDate'] = str(datetime.datetime.utcfromtimestamp(float(art['date'])))
        feeds.makeUnicode(art)
        articles.append(art)

    context['feeds'] = feeders
    context['articles'] = articles
    context['qs'] = qs

