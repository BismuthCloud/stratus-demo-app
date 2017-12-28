#!/usr/bin/env python3
from app import db
from geoalchemy2 import Geography, Raster
from shapely import wkb


class Source(db.Model):
    '''
    A specific source data may come from.
    E.g. NEXRAD L2, GFS, NAM, HRRR
    '''
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    src_url = db.Column(db.String(1024))
    last_updated = db.Column(db.DateTime)

    # Fields

    def serialize(self):
        return {"id": self.id,
                "name": self.name,
                "src_url": self.src_url,
                "last_updated": self.last_updated}


class Metric(db.Model):
    '''
    A metric that various source fields can have values for.
    E.g. temperature, precipitation, visibility
    '''
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    units = db.Column(db.String(16))

    def serialize(self):
        return {"id": self.id,
                "name": self.name,
                "units": self.units}


class SourceField(db.Model):
    '''
    A specific field inside of a source.
    E.g. Composite reflectivity @ entire atmosphere, 2m temps, visibility @ ground
    '''
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('source.id'))
    name = db.Column(db.String(255))
    metric_id = db.Column(db.Integer, db.ForeignKey('metric.id'))

    source = db.relationship('Source', backref='fields')
    metric = db.relationship('Metric')

    def serialize(self):
        return {"id": self.id,
                "source_id": self.source_id,
                "name": self.name,
                "metric_id": self.metric_id}

    def __repr__(self):
        return f"<SourceField id={self.id} name='{self.name}'>"


class Location(db.Model):
    '''
    A specific location that we have a lat/lon for.
    Currently just zipcodes.
    '''
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(Geography('Point,4326'))
    name = db.Column(db.String(512))

    def get_coords(self):
        '''
        :return: lon, lat
        '''
        point = wkb.loads(bytes(self.location.data))
        return point.x, point.y

    def serialize(self):
        coords = self.get_coords()

        return {"id": self.id,
                "lon": coords[0],
                "lat": coords[1],
                "name": self.name}


class CoordinateLookup(db.Model):
    '''
    Table that holds pre-computed coordinates for a given Location in a given source field.
    E.g. The zipcode 11111 corresponds to the point (x,y) in HRRR 2m temp rasters
    '''
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), primary_key=True)
    src_field_id = db.Column(db.Integer, db.ForeignKey('source_field.id'), primary_key=True)
    x = db.Column(db.Integer)
    y = db.Column(db.Integer)

    location = db.relationship('Location')
    src_field = db.relationship('SourceField')


class DataRaster(db.Model):
    '''
    Table that holds the actual raster data. One band per row.
    '''
    source_field_id = db.Column(db.Integer, db.ForeignKey('source_field.id'), primary_key=True)
    time = db.Column(db.DateTime, primary_key=True)
    rast = db.Column(Raster)  # Index automatically created for us

    src_field = db.relationship('SourceField')