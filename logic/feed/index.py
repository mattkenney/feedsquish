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

import feeds

def action(context):
    #LATER: implement "next" link for the next 50
    feeders = []
    for subid in feeds.redis.sort(context['user'] + "/subs", None, None, "*->feedName", None, False, True):
        feedName = feeds.redis.hget(subid, 'feedName')
        feeders.append({
            'feedName': feedName,
            'subid': subid
        })

    context['feeds'] = feeders

