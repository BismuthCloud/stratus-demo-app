#!/usr/bin/env python3
from flask import Blueprint, abort, jsonify, request
from datetime import datetime, timedelta
from geoalchemy2 import func as geofunc

import collections

from wx_explore.common import utils
from wx_explore.web.data.models import *
from wx_explore.web import app, db


api = Blueprint('api', __name__, url_prefix='/api')


@api.route('/sources')
def get_sources():
    res = []

    for source in Source.query.all():
        j = source.serialize()
        j['fields'] = [f.serialize() for f in source.fields]
        res.append(j)

    return jsonify(res)


@api.route('/source/<int:src_id>')
def get_source(src_id):
    source = Source.query.get(src_id)

    if not source:
        abort(404)

    j = source.serialize()
    j['fields'] = [f.serialize() for f in source.fields]

    return jsonify(j)


@api.route('/metrics')
def get_metrics():
    return jsonify([m.serialize() for m in Metric.query.all()])


@api.route('/location/search')
def get_location_from_query():
    search = request.args.get('q')

    if search is None or len(search) < 3:
        abort(400)

    search = search.replace('_', '\_').replace('%', '%%')
    search += '%'

    query = Location.query.filter(Location.name.ilike(search)).limit(10)

    return jsonify([l.serialize() for l in query.all()])


@api.route('/location/by_coords')
def get_location_from_coords():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if lat is None or lon is None:
        abort(400)

    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        abort(400)

    # TODO: may need to add distance limit if perf drops
    query = Location.query.order_by(Location.location.distance_centroid('POINT({} {})'.format(lon, lat)))

    return jsonify(query.first().serialize())


@api.route('/location/<int:loc_id>')
def get_location(loc_id):
    location = Location.query.get(loc_id)

    if location is None:
        abort(404)

    return jsonify(location.serialize())


@api.route('/location/<int:loc_id>/wx')
def wx_for_location(loc_id):
    location = Location.query.get(loc_id)

    if location is None:
        abort(404)

    requested_metrics = request.args.get('metrics')

    if requested_metrics:
        try:
            requested_metrics = requested_metrics.split(',')
        except AttributeError:
            abort(400)
        metrics = [Metric.query.get(i) for i in requested_metrics]
    else:
        metrics = Metric.query.all()

    now = datetime.utcnow()
    start = request.args.get('start')
    end = request.args.get('end')

    if start is None:
        start = now - timedelta(hours=1)
    else:
        try:
            start = datetime.utcfromtimestamp(int(start))
        except ValueError:
            abort(400)

        if not app.debug:
            if start < now - timedelta(days=1):
                start = now - timedelta(days=1)

    if end is None:
        end = now + timedelta(hours=12)
    else:
        try:
            end = datetime.utcfromtimestamp(int(end))
        except ValueError:
            abort(400)

        if not app.debug:
            if end > now + timedelta(days=7):
                end = now + timedelta(days=7)

    # Get all (time, value, metric)s for the time range and metrics desired
    #                this is 1 because each row's `rast` is only 1 row of data, not the entire 2d grid ---v
    data_points = db.session.query(DataRaster.run_time, DataRaster.valid_time, geofunc.ST_Value(DataRaster.rast, CoordinateLookup.x, 1).label("value"),
                                   SourceField,
                                   CoordinateLookup)\
                            .filter(DataRaster.valid_time >= start, DataRaster.valid_time < end)\
                            .filter(DataRaster.row == CoordinateLookup.y)\
                            .filter(CoordinateLookup.location_id == location.id) \
                            .filter(CoordinateLookup.src_field_id == SourceField.id) \
                            .filter(SourceField.id == DataRaster.source_field_id) \
                            .filter(SourceField.metric_id.in_(m.id for m in metrics))\
                            .all()

    # wx is a dict of unix_time->metrics, where each metric may have multiple values from different sources
    wx = {
        'ordered_times': set(),
        'data': collections.defaultdict(lambda: collections.defaultdict(list)),
    }

    for d in data_points:
        utime = utils.datetime2unix(d.valid_time)
        wx['ordered_times'].add(utime)
        wx['data'][utime][d.SourceField.metric.name].append({"value": d.value, "src_field_id": d.SourceField.id, "run_time": utils.datetime2unix(d.run_time)})

    wx['ordered_times'] = sorted(wx['ordered_times'])

    return jsonify(wx)