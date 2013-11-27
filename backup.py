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
import datetime

import boto

filename = '/var/lib/redis/redis.rdb'

def backup():
    now = datetime.datetime.utcnow()
    prefix = now.strftime('%w-%H')
    config = boto.pyami.config.Config()
    bucket_name = config.get('Redis', 'bucket')
    conn = boto.connect_s3()
    bucket = conn.get_bucket(bucket_name)
    key = boto.s3.key.Key(bucket)
    key.key = prefix + '/' + filename
    key.set_contents_from_filename(filename)

if __name__ == '__main__':
    backup()
