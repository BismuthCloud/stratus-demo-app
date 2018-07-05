from netCDF4 import Dataset
from scipy.spatial import cKDTree
import pygrib
import scipy.ndimage
import numpy

# Basically a singleton that all GriddedFields can use to share KDTrees
_KD_TREE_CACHE = {}

class Grid(object):
    def __init__(self, lats, lons, shape):
        self.lats = numpy.ravel(lats)
        self.lons = numpy.ravel(lons)
        self.shape = shape

    @property
    def lats_lons(self):
        return numpy.array([self.lats, self.lons])

    @property
    def pairs(self):
        return numpy.dstack([self.lats, self.lons])

    @staticmethod
    def from_unique_arrays(lats, lons):
        all_lats = numpy.repeat(lats, len(lons))
        all_lons = numpy.tile(lons, len(lats))
        return Grid(all_lats, all_lons, (len(lats), len(lons)))

    @staticmethod
    def from_ranges(lat_min, lat_max, lat_step, lon_min, lon_max, lon_step):
        lats = numpy.arange(lat_min, lat_max, lat_step)
        lons = numpy.arange(lon_min, lon_max, lon_step)
        return Grid.from_unique_arrays(lats, lons)


class GriddedField(object):
    def __init__(self, values, grid):
        self.grid = grid
        self.values = values
        if self.values.shape != grid.shape:
            self.values = self.values.reshape(grid.shape)
        self.lats = grid.lats
        self.lons = grid.lons
        self.shape = grid.shape

        self.kd_tree = _KD_TREE_CACHE.get(self.shape)

    @staticmethod
    def from_grib_msg(msg):
        """
        Construct a GriddedField from the given pygrib message
        """
        lats, lons = msg.latlons()
        gf = GriddedField(msg.values, Grid(lats, lons, msg.values.shape))
        return gf

    def k_nearest_points(self, coord_pairs, **kwargs):
        """
        Find 1 or more indexes into our values that are closest to the given lat,lon pairs.
        """
        if self.kd_tree is None:
            self.kd_tree = cKDTree(numpy.dstack([self.lats, self.lons])[0])
            _KD_TREE_CACHE[self.shape] = self.kd_tree

        idxs = self.kd_tree.query(coord_pairs, **kwargs)[1]
        if type(idxs) is int:  # if k=1, query returns a single int. Make it a list for the comprehension below
            idxs = [idxs]

        return [(idx // self.shape[1], idx % self.shape[1]) for idx in idxs]

    def nearest_point(self, lat, lon):
        """
        Find the x,y indexes into the given message's values that is closest to the given lat, lon
        """
        return self.k_nearest_points([(lat, lon)], k=1)[0]

    def resample_to_grid(self, grid):
        """
        Resample to a standard grid
        """
        grid_idxs = self.k_nearest_points(grid.pairs, k=1)
        # indexing expects [[x1, x2, x3], [y1, y2, y3]] so transpose [[x1, y1], [x2, y2]] to the expected form
        grid_idxs = grid_idxs.transpose()
        grid_vals = self.values[grid_idxs[0], grid_idxs[1]]
        return GriddedField(grid_vals, grid)

    def zoom(self, grid):
        zoomed_values = scipy.ndimage.zoom(self.values, (len(grid.lats)/self.shape[0], len(grid.lons)/self.shape[1]))
        return GriddedField(zoomed_values, grid)


class WindSkewProjector(object):
    def __init__(self, target_field, u_wind_field, v_wind_field):
        self.target_field = target_field
        self.u_wind_field = u_wind_field
        self.v_wind_field = v_wind_field

        if not (self.target_field.shape == self.u_wind_field.shape == self.v_wind_field.shape):
            raise ValueError("All fields must have the same shape")

        # Our starting array is the target
        self.values = self.target_field.values

    def _compute_new_indexes(self, step_duration):
        """
        For each index, compute the index whose value will be calculated to determine what value this index should hold
        after this step.

        For example, if our target field is a grid with 0.01deg spacing, the U vector wind field has an intensity of
        0.01deg/minute, there's no V wind, and our step_duration is 60 (seconds) then we'll return
        [[(0, 0), (0, 0), (0, 1)],
         [(1, 0), (1, 0), (1, 1)],
         [(2, 0), (2, 0), (2, 1)]]

        In that case, the longitudinal index (the second one) has been shifted back by 1 for each index pair.

        Then step() interpolates these and produces a new .values array, where in this case, all values have shifted
        east by a single element.
        """
        earth_radius = 6378 * 1000
        m_per_deg = 2*numpy.pi*earth_radius/360  # TODO: This should really be (earth_radius+height)

        coord_pairs = self.target_field.get_coord_pairs()

        new_idxs = numpy.empty(coord_pairs.shape)

        for idx,(lat,_) in enumerate(coord_pairs):
            lon_idx = idx % self.target_field.shape[1]
            lat_idx = idx // self.target_field.shape[1]

            # First, convert the m/s wind fields into deg/s
            # U is parallel with the equator, so latitude must be taken into account
            u_wind_ms = self.u_wind_field.values[lat_idx, lon_idx]/m_per_deg * numpy.cos(numpy.radians(lat))
            v_wind_ms = self.v_wind_field.values[lat_idx, lon_idx]/m_per_deg

            # Multiply by duration
            u_wind = u_wind_ms * step_duration
            v_wind = u_wind_ms * step_duration

            new_lon_idx -= u_wind
            new_lat_idx -= v_wind

            new_lon_idx = max(0, min(self.target_field.shape[1], new_lon_idx))
            new_lat_idx = max(0, min(self.target_field.shape[0], new_lat_idx))

            new_idxs[idx] = [new_lat_idx, new_lon_idx]

        return new_idxs

    def step(self, duration):
        wind_offset_coords = self._compute_new_indexes(duration)
        self.values = scipy.ndimage.map_coordinates(self.values, wind_offset_coords)
        return self.values

rad_ds = Dataset('/Users/nickgregory/Downloads/nc-ignore/wx/rta_testing/n0q_comp.nc')
rad_lats, rad_lons, rad_data = (rad_ds.variables.get(k)[...] for k in ('lat', 'lon', 'composite_n0q'))
rad = GriddedField(rad_data, Grid.from_unique_arrays(rad_lats, rad_lons))
print("Loaded radar composite")

hrrr_grib = pygrib.open('/Users/nickgregory/Downloads/nc-ignore/wx/rta_testing/hrrr.t01z.wrfsubhf01.grib2')
u_wind = GriddedField.from_grib_msg(hrrr_grib.select(name='U component of wind')[0])
print("Loaded U wind")
v_wind = GriddedField.from_grib_msg(hrrr_grib.select(name='V component of wind')[0])
print("Loaded V wind")

small_grid = Grid.from_ranges(
    rad_lats[0], rad_lats[-1], 0.03,
    rad_lons[0], rad_lons[-1], 0.03,
)

u_wind_resampled = u_wind.resample_to_grid(small_grid)
print("Resampled U wind")
v_wind_resampled = v_wind.resample_to_grid(small_grid)
print("Resampled V wind")

u_wind_zoomed = u_wind_resampled.zoom(rad.grid)
print("Zoomed U wind")
v_wind_zoomed = v_wind_resampled.zoom(rad.grid)
print("Zoomed V wind")

STEP_DURATION = 60 # seconds
projector = WindSkewProjector(rad, u_wind_zoomed, v_wind_zoomed)
for i in range(15):
    projector.step(STEP_DURATION)
    print(projector.values)
