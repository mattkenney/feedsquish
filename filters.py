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
import math

def compare(left, right):
    if left < right:
        return -1
    elif left > right:
        return 1
    return 0

def decode(value, special='%'):
    if value is None:
        return value
    src = unicode(value).encode('utf-8').split(special)
    buf = []
    buf.append(src[0])
    for s in src[1:]:
        try:
            n = int(s[0:2], 16)
            buf.append(chr(n))
            buf.append(s[2:])
        except ValueError, e:
            buf.append(s)
    return ''.join(buf)

def decode_segment(value):
    return decode(value, '_')

def default(var, default):
    return var if var else default

def encode(value, special='%', allowed=''):
    #logging.info("value = %s", repr(value))
    if value is None:
        return value
    text = unicode(value).encode('utf-8')
    buf = []
    for c in text:
        if (('a' <= c and c <= 'z') or ('A' <= c and c <= 'Z') or ('0' <= c and c <= '9') or (allowed.find(c) >= 0)) and c != special:
            buf.append(c)
        else:
            buf.append(special)
            buf.append("%02X" % ord(c))
    return ''.join(buf)

def encode_segment(value):
    return encode(value, '_', '-.')

def format_IEEE1541(value, unit='B'):
    mantissa = value
    exponent = 0
    while math.fabs(mantissa) >= 1024.0:
        exponent += 1
        mantissa /= 1024.0
    precision = 0
    if exponent > 0:
        precision = 3 - int(math.floor(math.log10(math.fabs(mantissa))))
        if precision < 0:
            precision = 0
    result = '%.*f ' % (precision, mantissa)
    suffix = ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi']
    if exponent < len(suffix):
        result += suffix[exponent]
    else:
        result += 'x 2^' + str(exponent*10) + ' '
    result += unit
    return result

def safelength(obj):
    result = 0
    try:
        result = len(obj)
    except:
        pass
    return result
