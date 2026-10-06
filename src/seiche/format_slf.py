"""
Extracts data from .slf files and format them in xr.DataArray.
"""

import os
import sys
from contextlib import suppress
from typing import cast

import numpy as np
import shapely
import shapely.ops
import xarray as xr
from matplotlib.tri import LinearTriInterpolator
from numpy import ma

from seiche.utils_da import generate_empty_da_from_bounds
from seiche.utils_qol import asinstance

RASTER_NDIMS = 3

if OPENTELEMAC_PATH := os.getenv("SEICHE_OPENTELEMAC_PATH"):
    # avoids appending a None to sys.path
    sys.path.append(OPENTELEMAC_PATH)

from data_manip.extraction.telemac_file import TelemacFile  # noqa: E402


class Slf(TelemacFile):
    """
    Inherited class from TelemacFile.

    The EPSG code is included, as well as other useful functions.
    """

    # initiate this class like any TelemacFile thx to *args, **kwargs
    def __init__(
        self,
        epsg: int,
        depth_varname: str,
        x_speed_varname: str,
        y_speed_varname: str,
        freesurf_varname: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        """
        Initialize Slf object.

        Parameters
        ----------
        epsg : int
            EPSG code for the spatial reference system.

        depth_varname: str
            Name of the variable in the .slf file that contains the depth data.

        x_speed_varname: str
            Name of the variable in the .slf file that contains the x speed data.

        y_speed_varname: str
            Name of the variable in the .slf file that contains the y speed data.

        freesurf_varname: str
            Name of the variable in the .slf file that contains the free surface data.

        *args
            Additional positional arguments for TelemacFile.

        **kwargs
            Additional keyword arguments for TelemacFile.

        """
        super().__init__(*args, **kwargs)
        # adding epsg information to the Telemac File
        if not isinstance(epsg, int):
            msg = "'epsg' must be an integer"
            raise TypeError(msg)
        self.epsg = epsg
        self.depth_varname = depth_varname
        self.x_speed_varname = x_speed_varname
        self.y_speed_varname = y_speed_varname
        self.freesurf_varname = freesurf_varname
        with suppress(TypeError):
            self.extent = self.get_delineation()

    def get_delineation(self) -> shapely.Polygon:
        """
        Compute the exterior polygon of the mesh triangulation in the same CRS.

        Returns
        -------
        shapely.Polygon
            Polygon representing the mesh extent. Can be a shapely.MultiPolygon
            for complex or masked meshes (e.g. several disconnected parts).

        Notes
        -----
        My refactoring of Thanh Huy Nguyen's function 'delineation_T2D_bounds'
        (tools4telemac gitlab).

        """
        # take mask into account, changes nothing if no mask
        triangles = np.ma.asarray(self.tri.get_masked_triangles())
        triangles = triangles[~np.ma.getmaskarray(triangles).any(axis=1)]
        # one polygon per triangle, unioned to get the mesh extent
        polygons = [
            shapely.geometry.Polygon(np.c_[self.meshx[t], self.meshy[t]])
            for t in triangles
        ]
        # shapely ships no type hints: the union may also be a MultiPolygon
        return cast("shapely.Polygon", shapely.ops.unary_union(polygons))

    def interp_values_on_grid(
        self,
        node_values: np.ndarray,
        grid: xr.DataArray,
    ) -> xr.DataArray:
        """
        Interpolate the given node values on a grid (xr.DataArray of shape (1, n, m)).

        Parameters
        ----------
        node_values : np.ndarray
            1D array of length self.npoin2 contaning values to interpolate.

        grid : xr.DataArray
            xr.DataArray with shape (1, n, m) representing the target raster
            grid for interpolation
            This shape comes from a raster opened with rioxarray, e.g., via
            rxr.open_rasterio(...)

        Returns
        -------
        xr.DataArray
            The grid, filled with interpolated data.

        """
        if not ((len(grid.values.shape) == RASTER_NDIMS) and grid.values.shape[0] == 1):
            msg = (
                "grid xr.DataArray.values must be of shape (1, n, m) "
                "-> like 1 band raster read with rxr.open_rasterio"
            )
            raise ValueError(
                msg,
            )
        if node_values.shape != (self.npoin2,):
            msg = f"nodesValues is not of shape ({self.npoin2},)"
            raise ValueError(msg)
        # reproject the grid to match selafin epsg
        grid = asinstance(grid.rio.reproject(f"EPSG:{self.epsg}").copy(), xr.DataArray)
        # building the interpolator to rasterize node_values to match grid
        tri_mesh = self.tri
        # only linear interpolator for now
        interpolator = LinearTriInterpolator(tri_mesh, node_values)
        # > interpolator = matplotlib.tri.CubicTriInterpolator(tri_mesh, node_values)
        # values is empty of shape (1, n, m)
        values = np.empty_like(grid.values)
        # generating points grid to interpolate values at
        points = np.array([[[x, y] for x in grid.x.values] for y in grid.y.values])
        # actual interpolation of already aggregated values
        masked_values = interpolator(points[:, :, 0], points[:, :, 1])
        # values came in a masked array, that we unmask and fill with np.nan values
        values[0] = ma.filled(masked_values, fill_value=np.nan)
        # putting values in a data array of same metadata as grid
        return asinstance(grid.copy(data=values), xr.DataArray)

    def generate_grid_on_extent(self, pixel_size: int) -> xr.DataArray:
        """
        Generate a regular grid on the given extent.

        Parameters
        ----------
        pixel_size : int
            Pixel size in meters (or °, depending on EPSG) for the generated grid cells.

        """
        return generate_empty_da_from_bounds(self.extent.bounds, pixel_size, self.epsg)

    def interp_max_depth_on_grid(self, grid: xr.DataArray) -> xr.DataArray:
        """
        Get H(x, y), the maximum depth field from a slf file.

        Steps are:
            1. Gather data on every node for all timesteps.
            2. Get the max (time-wise) depth value per node.
            3. Interpolate the node values on a grid.

        Parameters
        ----------
        grid : xr.DataArray
            Grid on which to interpolate the values.

        Returns
        -------
        xr.DataArray
            Interpolated max depth values on the grid.

        """
        depth_series = self.get_timeseries_on_nodes(
            self.depth_varname,
            list(range(self.npoin2)),
        )
        max_depth = np.max(depth_series, axis=1)
        return self.interp_values_on_grid(max_depth, grid)

    def interp_max_freesurf_on_grid(self, grid: xr.DataArray) -> xr.DataArray:
        """
        Get F(x, y), the maximum free surface field from a slf file.

        Steps are:
            1. Gather data on every node for all timesteps.
            2. Get the max (time-wise) free surf value per node.
            3. Interpolate the node values on a grid.

        Parameters
        ----------
        grid : xr.DataArray
            Grid on which to interpolate the values.

        Returns
        -------
        xr.DataArray
            Interpolated max depth values on the grid.

        """
        freesurf_series = self.get_timeseries_on_nodes(
            self.freesurf_varname,
            list(range(self.npoin2)),
        )
        max_freesurf = np.max(freesurf_series, axis=1)
        return self.interp_values_on_grid(max_freesurf, grid)

    def interp_duration_on_grid(
        self,
        grid: xr.DataArray,
        threshold: float,
    ) -> xr.DataArray:
        """
        Get T(x, y), the duration field from a slf file.

        Steps are:
            1. Gather data on every node for all timesteps.
            2. Count for each node all timesteps where depth >= threshold.
            3. Convert it in seconds.
            4. Interpolate the node values on a grid.

        Parameters
        ----------
        grid : xr.DataArray
            Grid on which to interpolate the values.

        threshold : float
            Threshold value to consider a point as flooded based on depth.

        Returns
        -------
            xr.DataArray: Interpolated duration values on the grid.

        """
        time_intervals = np.diff(self.times)
        depth_series = self.get_timeseries_on_nodes(
            self.depth_varname,
            list(range(self.npoin2)),
        )
        flooded_mask = depth_series[:, :-1] >= threshold
        duration = np.sum(time_intervals * flooded_mask, axis=1)
        return self.interp_values_on_grid(duration, grid)

    def interp_max_speed_on_grid(self, grid: xr.DataArray) -> xr.DataArray:
        """
        Get V(x, y), the max speed field from a slf file.

        Steps are:
            1. Gather x speed and y speed data on every node for all timesteps.
            2. For each time step, convert it to a speed value (sqrt(x^2 + y^2)).
            3. Get the max (time-wise) speed value per node.
            4. Interpolate the node values on a grid.

        Parameters
        ----------
        grid : xr.DataArray
            Grid on which to interpolate the values.

        Returns
        -------
        xr.DataArray
            Interpolated duration values on the grid.

        """
        x_speed_series = self.get_timeseries_on_nodes(
            self.x_speed_varname,
            list(range(self.npoin2)),
        )
        y_speed_series = self.get_timeseries_on_nodes(
            self.y_speed_varname,
            list(range(self.npoin2)),
        )
        maxspeed = np.max(np.sqrt(x_speed_series**2 + y_speed_series**2), axis=1)
        return self.interp_values_on_grid(maxspeed, grid)
