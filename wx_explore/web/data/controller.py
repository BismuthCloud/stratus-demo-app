from datetime import datetime, timedelta
from flask import Blueprint, abort, jsonify, request

import array
import collections

from wx_explore.common.models import (
    Source,
    Location,
    Metric,
    FileBandMeta,
)
from wx_explore.common.location import get_xy_for_coord, proj_shape
from wx_explore.common.storage import get_s3_bucket
from wx_explore.common.utils import datetime2unix
from wx_explore.web import app


api = Blueprint('api', __name__, url_prefix='/api')


@api.route('/sources')
def get_sources():
    """
    Get all sources that data points can come from.
    :return: List of sources.
    """
    res = []

    for source in Source.query.all():
        j = source.serialize()
        j['fields'] = [f.serialize() for f in source.fields]
        res.append(j)

    return jsonify(res)


@api.route('/source/<int:src_id>')
def get_source(src_id):
    """
    Get data about a specific source.
    :param src_id: The ID of the source.
    :return: An object representing the source.
    """
    source = Source.query.get_or_404(src_id)

    j = source.serialize()
    j['fields'] = [f.serialize() for f in source.fields]

    return jsonify(j)


@api.route('/metrics')
def get_metrics():
    """
    Get all metrics that data points can be.
    :return: List of metrics.
    """
    return jsonify([m.serialize() for m in Metric.query.all()])


@api.route('/location/search')
def get_location_from_query():
    """
    Search locations by name prefix.
    :return: A list of locations matching the search query.
    """
    search = request.args.get('q')

    if search is None or len(search) < 2:
        abort(400)

    # Fixes basic weird results that could come from users entering '\'s, '%'s, or '_'s
    search = search.replace('\\', '\\\\').replace('_', '\_').replace('%', '\%')
    search += '%'

    query = Location.query.filter(Location.name.ilike(search)).limit(10)

    return jsonify([l.serialize() for l in query.all()])


@api.route('/wx')
def wx_for_location():
    """
    Gets the weather for a specific location, optionally limiting by metric and time.
    at that time.
    """
    lat = float(request.args['lat'])
    lon = float(request.args['lon'])

    if lat > 90 or lat < -90 or lon > 180 or lon < -180:
        abort(400)

    requested_metrics = request.args.getlist('metrics')

    if requested_metrics:
        metrics = [Metric.query.get(i) for i in requested_metrics]
    else:
        metrics = Metric.query.all()

    now = datetime.utcnow()
    start = request.args.get('start', type=int)
    end = request.args.get('end', type=int)

    if start is None:
        start = now - timedelta(hours=1)
    else:
        start = datetime.utcfromtimestamp(start)

        if not app.debug:
            if start < now - timedelta(days=1):
                start = now - timedelta(days=1)

    if end is None:
        end = now + timedelta(hours=12)
    else:
        end = datetime.utcfromtimestamp(end)

        if not app.debug:
            if end > now + timedelta(days=7):
                end = now + timedelta(days=7)

    requested_source_fields = set()
    for metric in metrics:
        for sf in metric.fields:
            requested_source_fields.add(sf)

    valid_source_fields = set()
    locs = {}
    for sf in requested_source_fields:
        loc = get_xy_for_coord(sf.projection, (lat,lon))
        if loc is not None:
            locs[sf.projection.id] = loc
            valid_source_fields.add(sf)

    fbms = FileBandMeta.query.filter(
        FileBandMeta.source_field_id.in_([sf.id for sf in valid_source_fields]),
        FileBandMeta.valid_time >= start,
        FileBandMeta.valid_time < end,
    ).all()

    # Gather all files we need data from
    file_metas = set(fbm.file_meta for fbm in fbms)
    file_contents = {}

    # Read them in
    # TODO: do all of these in parallel since most time will probably be spent blocked on FIO
    s3 = get_s3_bucket()
    for fm in file_metas:
        x, y = locs[fm.projection.id]
        n_x = proj_shape(fm.projection)[1]
        loc_chunks = (y * n_x) + x

        obj = s3.Object(fm.file_name)
        start = loc_chunks * fm.loc_size
        end = (loc_chunks + 1) * fm.loc_size
        file_contents[fm.file_name] = obj.get(Range=f'bytes={start}-{end-1}')['Body'].read()

    # filebandmeta -> values
    data_points = {}

    for fbm in fbms:
        raw = file_contents[fbm.file_meta.file_name][fbm.offset:fbm.offset+(4*fbm.vals_per_loc)]
        data_values = array.array("f", raw).tolist()
        data_points[fbm] = data_values

    # valid time -> data points
    datas = collections.defaultdict(list)

    for fbm, values in data_points.items():
        datas[datetime2unix(fbm.valid_time)].append({
            'run_time': datetime2unix(fbm.run_time),
            'src_field_id': fbm.source_field_id,
            'value': values[0],  # TODO
        })

    wx = {
        'data': datas,
        'ordered_times': sorted(datas.keys()),
    }

    return jsonify(wx)
