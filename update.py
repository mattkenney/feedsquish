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
import calendar
import datetime
import logging
import time

import feedparser

import feeds
import filters

def updateFeed(feedUrl, now, cutoff):
    print 'parsing ', feedUrl
    parser = feedparser.parse(feedUrl)#, agent='Mozilla/4.0 (compatible; MSIE 7.0b; Windows NT 6.0)')
    print 'status ', str(parser.status)
#        if parser.status == 500:
#            print news.escape_xml(parser.data)

    feedid = "feed/" + filters.encode_segment(feedUrl)
    for entry in parser.entries:
        link = entry.get('link', '')

        if not link:
            continue;
        artid = "art/" + filters.encode_segment(link)
        if feeds.redis.exists(artid):
            print 'skipping', link
            continue;

        print 'saving', link
        art = {}
        art['name'] = entry.get('title', '')
        art['guid'] = entry.get('guid', '')
        art['date'] = now
        if entry.has_key('published_parsed') and entry.published_parsed:
            art['date'] = calendar.timegm(entry.published_parsed)
        elif entry.has_key('date_parsed') and entry.date_parsed:
            art['date'] = calendar.timegm(entry.date_parsed)
        art['category'] = entry.get('category', '')
        feeds.redis.hmset(artid, art)
        feeds.redis.zadd(feedid, art['date'], artid)

    print 'purging ', feedUrl
    for artid in feeds.redis.zrangebyscore(feedid, "-inf", cutoff):
        feeds.redis.delete(artid)
    feeds.redis.zremrangebyscore(feedid, "-inf", cutoff)

def updateAll():
    now = int(time.time())
    print now
    cutoff = now - (60 * 24 * 60 * 60)
    feeds.redis.zremrangebyscore("feeds", "-inf", cutoff)
    for feedUrl in feeds.redis.zrange("feeds", 0, -1):
        try:
            updateFeed(feedUrl, now, cutoff)
        except Exception, e:
            print e

if __name__ == '__main__':
    updateAll()

