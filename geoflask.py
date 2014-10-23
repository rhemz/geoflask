"""
geoFlask
"""

import os
import json
import socket

from ratelimit import ratelimit, get_view_rate_limit

from flask import Flask, url_for, request, g, render_template, jsonify, Response
from redis import Redis
import pygeoip


ROOT_DIR = os.path.dirname(os.path.realpath(__file__)) + '/'
CONFIG_FILE = os.path.join(ROOT_DIR, 'geoflask.conf')

app = Flask(__name__)
redis = Redis()


def load_config(cfg=None):
    """
    (Re)loads configuration
    """
    if cfg is None:
        cfg = CONFIG_FILE
    with open(cfg) as f:
        config = json.load(f)
    return config

config = load_config()

@app.route('/', defaults={'ip': None})
@app.route('/<string:ip>')
@ratelimit(limit=config['rate_limit'], per=config['rate_limit_timeframe'])
def ip(ip):
    if ip is None:
        if not request.headers.getlist("X-Forwarded-For"):
            ip = request.remote_addr
        else:
            ip = request.headers.getlist("X-Forwarded-For")[0]

    try:
        socket.inet_aton(ip)
    except:
        return 'Not an IP', 400

    key = '%s/%s/' % (config['redis_lookup_prefix'], ip)

    c = redis.get(key)
    g.from_cache = True if c is not None else False

    if g.from_cache:
        return Response(response=c, status=200, mimetype='application/json')
    else:
        geo = pygeoip.GeoIP(config['city_db'])
        geo_data = json.dumps(geo.record_by_addr(ip))
        redis.set(key, geo_data)
        return Response(response=geo_data, status=200, mimetype='application/json')


@app.after_request
def after_request(response):
    h = response.headers
    h.add('X-From-Cache', getattr(g, 'from_cache', False))

    limit = get_view_rate_limit()
    if limit and limit.send_x_headers:
        h.add('X-RateLimit-Remaining', str(limit.remaining))
        h.add('X-RateLimit-Limit', str(limit.limit))
        h.add('X-RateLimit-Reset', str(limit.reset))
    return response


def main():
    app.run(config['address'], port=config['port'], debug=config['debug'])


if __name__ == '__main__':
    main()
