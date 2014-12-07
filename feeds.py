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
import base64
import cgi
import cookielib
import datetime
import hashlib
import logging
import pprint
import re
import time
import traceback
import urllib2
import urlparse
import uuid
import xml.dom.minidom
from xml.sax.saxutils import escape

import redis.client

import bs4 as BeautifulSoup
import xpath

import filters

hex_char_entity = re.compile('&#x([0-9a-fA-F]+);')
unread = datetime.datetime.max.isoformat()

redis = redis.client.StrictRedis()

def adjust_url(url, sub):
    if sub:
        if (sub['prefixRemove'] or sub['prefixAdd']) and url.startswith(sub['prefixRemove']):
            url = sub['prefixAdd'] + url[len(sub['prefixRemove']):]
        if (sub['suffixRemove'] or sub['suffixAdd']) and url.endswith(sub['suffixRemove']):
            url = url[:(len(url) - len(sub['suffixRemove']))]
            if sub['suffixAdd'][:1] == '?' and '?' in url:
                url += '&' + sub['suffixAdd'][1:]
            else:
                url += sub['suffixAdd']
    return url

class LoggingHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
    def __init__(self, sub, log):
        self.sub = sub
        self.log = log

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        newurl = adjust_url(newurl, self.sub)
        if self.log is not None:
            self.log.append('redirecting to: ')
            self.log.append(newurl)
            self.log.append('\n')
        return urllib2.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, hdrs, newurl)

def get_article_content(articleUrl, articleGuid, sub, lstLog=None):
    result = None

#    sys.stderr.write(str(articleUrl) + '\n')
#    sys.stderr.flush()

    url = articleUrl

    # optionally modify URL before fetching the article
    if sub and articleGuid and sub['useGuid'] == '1':
        url = articleGuid
    url = adjust_url(url, sub)

    # use cached copy if present
    key = url
    if sub and sub['xpath']:
        key = key + ' ' + sub['xpath']
    key = "page/" + filters.encode_segment(key)
    if not lstLog:
        result = redis.get(key)
        if result:
            return result.decode('utf-8')

    raw = None
    try:
        if lstLog:
            lstLog.append('fetching url: ')
            lstLog.append(url)
            lstLog.append('\n')

        # fetch the article
        before = time.clock()
        jar = cookielib.CookieJar()
        proc = urllib2.HTTPCookieProcessor(jar)
        redir = LoggingHTTPRedirectHandler(sub, lstLog)
        opener = urllib2.build_opener(proc, redir)
        opener.addheaders.append(('Accept', '*/*'))
        f = opener.open(url)
        raw = f.read()
        base = f.geturl()
        mime, params = cgi.parse_header(f.info().getheader('Content-Type'))
        encoding = params.get('charset')#, 'ISO-8859-1')
        f.close()

        if lstLog:
            lstLog.append(str(len(raw)))
            lstLog.append(' bytes retrieved in ')
            lstLog.append(str(time.clock() - before))
            lstLog.append(' seconds, encoding ')
            lstLog.append(str(encoding))
            lstLog.append('\n')

        # tag soup parse the article
        before = time.clock()
        src = BeautifulSoup.BeautifulSoup(raw, "html5lib", from_encoding=encoding)

        if lstLog:
            lstLog.append('parse ')
            lstLog.append(str(time.clock() - before))
            lstLog.append(' seconds\n')

        # sanitize the article markup - remove script, style, and more
        # also convert to xml.dom.minidom so we can use xpath
        before = time.clock()
        doc = soup2dom(src)

        if lstLog:
            lstLog.append('sanitize ')
            lstLog.append(str(time.clock() - before))
            lstLog.append(' seconds\n')

        # extract the parts we want
        before = time.clock()
        parts = []
        if sub and sub['xpath']:
            for path in sub['xpath'].split('\n'):
                parts.extend(xpath.find(path, doc))
        else:
            parts.append(doc.documentElement)

        if lstLog:
            lstLog.append('xpath ')
            lstLog.append(str(time.clock() - before))
            lstLog.append(' seconds\n')
            lstLog.append('xpath ')
            lstLog.append(str(len(parts)))
            lstLog.append(' parts\n')

        # remove class and id attributes so they won't conflict with ours
        # this makes the content smaller too
        # we do this after xpath so xpath can use class and id
        before = time.clock()
        for tag in doc.getElementsByTagName('*'):
            if tag.hasAttribute('class'):
                tag.removeAttribute('class')
            if tag.hasAttribute('id'):
                tag.removeAttribute('id')
            if tag.nodeName == 'a' and tag.hasAttribute('href'):
                tag.setAttribute('target', '_blank')

        if lstLog:
            lstLog.append('clean ')
            lstLog.append(str(time.clock() - before))
            lstLog.append(' seconds\n')

        # make relative URLs absolute so they work in our site
        before = time.clock()
        cache = {}
        for part in parts:
            for attr in [ 'action', 'background', 'cite', 'classid', 'codebase', 'data', 'href', 'longdesc', 'profile', 'src', 'usemap' ]:
                for tag in xpath.find('.//*[@' + attr + ']', part):
                    value = tag.getAttribute(attr)
                    absolute = urlparse.urljoin(base, value)
                    tag.setAttribute(attr, absolute)

        if lstLog:
            lstLog.append('make urls absolute ')
            lstLog.append(str(time.clock() - before))
            lstLog.append(' seconds\n')

        # convert to string
        before = time.clock()
        result = u''
        for part in parts:
            result += u'<div>'
            if part.nodeType == 2:
                result += part.nodeValue
            else:
                result += part.toxml('utf-8').decode('utf-8')
            result += u'</div>'

        if lstLog:
            lstLog.append('to string ')
            lstLog.append(str(time.clock() - before))
            lstLog.append(' seconds\n')

        if lstLog:
            lstLog.append('article size: ')
            lstLog.append(filters.format_IEEE1541(len(result)))
            lstLog.append('\n')

        redis.setex(key, 20*60, result)

        if lstLog and len(result) == 0:
            result += '<pre>\n'
            result += escape('\n'.join(lstLog))
            result += '\n</pre>'

    except Exception, err:
        logging.error("%s", pprint.pformat(err))
        text = str(err)
        if lstLog:
            lstLog.append('exception:\n')
            lstLog.append(text)
            lstLog.append('stack:\n')
            lstLog.append(traceback.format_exc())
            lstLog.append('source:\n')
            lstLog.append(repr(raw))
            lstLog.append('\n')
        if result:
            result += '\n'
        else:
            result = ''
        result += '<pre>\n'
        result += escape(str(url))
        result += '\n\n'
        result += escape(text)
        result += '\n</pre>\n<!--\n'
        result += escape(traceback.format_exc())
        result += '\n-->'

    return result

def soup2dom(src, dst=None, doc=None):
    if doc and not dst:
        dst = doc.documentElement
    # elements have contents attribute we need to enumerate
    if hasattr(src, 'contents'):
        tag = src.name.lower()
        # silent element blacklist
        if tag in [ 'head', 'link', 'meta', 'script', 'style' ]:
            return doc
        # element blacklist with placeholder
        if tag in [ 'applet', 'embed', 'frame', 'object' ]:
            if dst:
                dst.appendChild(doc.createTextNode(' [' + tag + '] '))
            return doc
        attrs = dict()
        for key in src.attrs:
            value = src[key]
            if isinstance(value, list):
                value = u' '.join(value)
            if not isinstance(value, unicode) or value.lower().startswith(u'javascript:'):
                value = u''
            attrs[key] = value
        if doc:
            # create the element
            if tag == 'iframe':
                # blacklist iframe, but show link
                dst.appendChild(doc.createTextNode(' ['))
                a = doc.createElement('a')
                dst.appendChild(a)
                if 'src' in attrs:
                    a.setAttribute('href', attrs['src'])
                a.appendChild(doc.createTextNode('iframe'))
                dst.appendChild(doc.createTextNode('] '))
                return doc
            # we're going to use this inside another document
            # so we switch [body] to [div]
            if tag == 'body':
                tag = 'div'
            # create the element and descend
            elem = doc.createElement(tag);
            dst.appendChild(elem)
            dst = elem
        elif src.__class__.__name__ != 'BeautifulSoup':
            # when we get the first element create a [div] rooted document to build on
            doc = xml.dom.minidom.getDOMImplementation().createDocument(None, 'div', None)
            dst = doc.documentElement
            if tag == 'iframe':
                return soup2dom(src, dst, doc)
            if tag != 'html':
                elem = doc.createElement(tag)
                dst.appendChild(elem)
                dst = elem
        # we want href first according to Google pagespeed
        if 'href' in attrs:
            dst.setAttribute('href', attrs['href'])
        # then the rest of the attributes
        for key in sorted(attrs.keys()):
            # blacklist style and event handlers
            if key == 'href' or key == 'style' or key.startswith('on'):
                continue
            dst.setAttribute(key, attrs[key])
        # recurse into contents
        for content in src.contents:
            doc = soup2dom(content, dst, doc)
        # put a one space comment into empty elements we don't want minidom to minimize
        # which is any element not listed as empty in HTML5
        if dst and not dst.hasChildNodes() and not tag in [ 'area', 'base', 'basefont', 'br', 'col', 'command', 'embed', 'frame', 'hr', 'img', 'input', 'isindex', 'keygen', 'link', 'meta', 'param', 'source', 'track', 'wbr' ]:
            dst.appendChild(doc.createComment(' '))
    elif dst and src.__class__.__name__ == 'NavigableString':
        # append text; we don't do isinstance because we want to lose comments
        dst.appendChild(doc.createTextNode(src))
    return doc

def makeUnicode(target):
    for key in target.keys():
        value = target[key]
        if isinstance(value, str):
            target[key] = value.decode('utf-8')
    return target

def update_user(userid):
    logging.info('updating articles for user %s' , userid)
    now = time.time()
    cutoff = now - (60 * 24 * 60 * 60)
    update = redis.hget(userid, 'update')
    for subid in redis.smembers(userid + "/subs"):
        feedUrl = redis.hget(subid, "feedUrl")
        if feedUrl:
            # update the feed's access time
            redis.zadd('feeds', now, feedUrl)
            # get the new article IDs
            args = []
            feedid = "feed/" + filters.encode_segment(feedUrl)
            for artid, score in redis.zrange(feedid, 0, -1, None, True):
                if not redis.zscore(subid + "/read", artid):
                    args.append(score)
                    args.append(artid)
            # copy the new article IDs to the unread zset
            if args:
                redis.zadd(subid + "/unread", *args)
        # purge articles older then 60 days
        redis.zremrangebyscore(subid + "/unread", "-inf", cutoff)
        redis.zremrangebyscore(subid + "/read", "-inf", cutoff)
    # save now as the last update time
    redis.hset(userid, 'update', now)

def update_user_maybe(userid):
    key = "update/" + filters.encode_segment(userid)
    if True or not redis.exists(key):
        update_user(userid)
        redis.setex(key, 600, "1")
