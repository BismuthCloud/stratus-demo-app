#!/usr/bin/env python3
from geoalchemy2 import Geography, Raster
from shapely import wkb
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Source(Base):
    """
    A specific source data may come from.
    E.g. NEXRAD L2, GFS, NAM, HRRR
    """
    __tablename__ = "source"

    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    src_url = Column(String(1024))
    last_updated = Column(DateTime)

    # Fields are backref'd

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "src_url": self.src_url,
            "last_updated": self.last_updated,
        }

    def __repr__(self):
        return f"<Source id={self.id} name='{self.name}'>"


class Metric(Base):
    """
    A metric that various source fields can have values for.
    E.g. temperature, precipitation, visibility
    """
    __tablename__ = "metric"

    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    units = Column(String(16))

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "units": self.units,
        }

    def __repr__(self):
        return f"<Metric id={self.id} name='{self.name}'>"


class SourceField(Base):
    """
    A specific field inside of a source.
    E.g. Composite reflectivity @ entire atmosphere, 2m temps, visibility @ ground
    """
    __tablename__ = "source_field"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('source.id'))

    idx_short_name = Column(String(15))  # e.g. TMP, VIS
    idx_level = Column(String(255))  # e.g. surface, 2 m above ground
    grib_name = Column(String(255))  # e.g. 2 metre temperature

    metric_id = Column(Integer, ForeignKey('metric.id'))

    source = relationship('Source', backref='fields')
    metric = relationship('Metric', backref='fields')

    def serialize(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "grib_name": self.grib_name,
            "metric_id": self.metric_id,
        }

    def __repr__(self):
        return f"<SourceField id={self.id} name='{self.name}'>"


class Location(Base):
    """
    A specific location that we have a lat/lon for.
    Currently just zipcodes.
    """
    __tablename__ = "location"

    id = Column(Integer, primary_key=True)
    location = Column(Geography('Point,4326'))
    name = Column(String(512))

    def get_coords(self):
        """
        :return: lon, lat
        """
        point = wkb.loads(bytes(self.location.data))
        return point.x, point.y

    def serialize(self):
        coords = self.get_coords()

        return {
            "id": self.id,
            "lon": coords[0],
            "lat": coords[1],
            "name": self.name,
        }

    def __repr__(self):
        return f"<Location id={self.id} name='{self.name}'>"


class CoordinateLookup(Base):
    """
    Table that holds a lookup from location to grid x,y for the given source field.
    """
    __tablename__ = "coordinate_lookup"

    src_field_id = Column(Integer, ForeignKey('source_field.id'), primary_key=True)
    location_id = Column(Integer, ForeignKey('location.id'), primary_key=True)
    x = Column(Integer)
    y = Column(Integer)

    src_field = relationship('SourceField')
    location = relationship('Location')


class DataRaster(Base):
    """
    Table that holds the "raw" raster data.
    """
    __tablename__ = "data_raster"

    source_field_id = Column(Integer, ForeignKey('source_field.id'), primary_key=True)
    valid_time = Column(DateTime, primary_key=True)
    run_time = Column(DateTime, primary_key=True)
    row = Column(Integer, primary_key=True)
    rast = Column(Raster)

    src_field = relationship('SourceField')

    def __repr__(self):
        return f"<DataRaster source_field_id={self.source_field_id} valid_time={self.valid_time} run_time={self.run_time} row={self.row}>"


class LocationData(Base):
    """
    Table that holds denormalized data for a given location.

    The data stored is a JSON dictionary mapping timestamps -> values, which are a
    list of objects, each have the SourceField they come from, the run time of the model,
    and the actual field value.
    """
    __tablename__ = "location_data"

    location_id = Column(Integer, ForeignKey('location.id'), primary_key=True)
    values = Column(JSON)
