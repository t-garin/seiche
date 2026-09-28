"""
Miscellaneous experimental helpers for manipulating Selafin (`.slf`) files.

These used to live as methods of `Slf` in `src/seiche/format_slf.py`, but
none of them are used by the SEICHE pipeline. They are kept here for ad-hoc
experiments.

Requires the OpenTelemac python API on `sys.path` (set `SEICHE_OPENTELEMAC_PATH`
and import `Slf`), see `docs/contributing.md`.
"""

import datetime
import itertools
import os

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
import xarray as xr

from seiche.format_slf import Slf


class SlfMisc(Slf):
    """
    Subclass of `Slf` carrying experimental helper methods.

    Not used by the main pipeline; provided for interactive/scripted experiments
    on `.slf` files (downsampling, boolean masks, variable subsets,
    centerlines, ...).
    """

    def timestep2time(self, timestep: int) -> pd.Timestamp:
        """
        Convert a timestep index to a pandas Timestamp based on file origin.

        Parameters
        ----------
        timestep : int
            Index of the timestep to convert.

        Returns
        -------
        pd.Timestamp
            Corresponding datetime for the given timestep.

        """
        assert type(timestep) is int, "timestep is not an int"
        assert timestep in range(0, self.get_data_ntimestep()), (
            "timestep is not in the file"
        )
        origin = pd.to_datetime(datetime.datetime(*self.datetime))
        seconds = pd.to_timedelta(self.times[timestep], unit="s")
        return origin + seconds

    def interp_values_on_points(
        self,
        varname: str,
        timestep: int,
        points: list[tuple[float, float] | list[float, float]],
    ) -> np.ndarray:
        """
        For a given var and timestep, interpolates the values on specified 'points'.

        Parameters
        ----------
        varname : str
            Variable to interpolate.

        timestep : int
            Timestep for which to interpolate.

        points : list[tuple[float, float] | list[float, float]]
            Points must be specified in x,y coords matching the selafin EPSG

        Returns
        -------
        np.ndarray
            Containing the values in the same order as the points.

        """
        tri_mesh = self.tri
        tri_values = self.get_data_value(varname, timestep)
        interpolator = matplotlib.tri.LinearTriInterpolator(
            tri_mesh, tri_values
        )
        # > interpolator = matplotlib.tri.CubicTriInterpolator(tri_mesh, tri_values)
        return interpolator(
            [point[0] for point in points], [point[1] for point in points]
        )

    def polygonize_by_threshold(
        self, slfvar: str, threshold: float, timestep: int
    ) -> list[shapely.Polygon]:
        """
        From a given slf file, returns for a given timestep a shapely.Polygon corresponding to the places where the value of slfvar is above or equal a certain threshold.

        Parameters
        ----------
        slfvar : str
            See function desc.

        threshold : float
            See function desc.

        timestep : int
            See function desc.

        Returns
        -------
        list[shapely.Polygon]
            Areas were the value is above the thresh.

        """
        # loading values for specified variable
        values = self.get_data_value(slfvar, timestep)
        # generating the boolean contour, True if values between threshold and 9999
        contour = plt.tricontourf(self.tri, values, levels=[threshold, 9999])
        # extracting polygons from the contour
        polygons = [shapely.Polygon(seg) for seg in contour.allsegs[0]]
        # separating polygons between filled and holes, based on the rotation of their points
        # --> counter clockwise (ccw) polygons = filled
        ccwpolys = [
            polygon for polygon in polygons if shapely.is_ccw(polygon.exterior)
        ]
        # --> clockwise (cw) polygons = holes
        cwpolys = [
            polygon
            for polygon in polygons
            if not shapely.is_ccw(polygon.exterior)
        ]
        # resulting geometry is : ccw polygons - cw polygons
        res = shapely.difference(
            shapely.unary_union(ccwpolys), shapely.unary_union(cwpolys)
        )

        # res removes 'islands', that are ccw polygons inside a cw polygon (non-hole inside a hole)
        # to add them back we look for these islands and perform a union with the previous geometry
        # (this function does not account for islands within islands ...etc.)
        islands = []
        for cwp in cwpolys:  # for each hole
            for ccwp in ccwpolys:  # for each non-hole
                if cwp.covers(ccwp):
                    islands.append(ccwp)

        res = shapely.unary_union([res, *islands])

        return res

    def new_slf_with_suffix(
        self, suffix: str = "_copy", overwrite: bool = False
    ):
        """
        Create a new empty writeable Selafin file with same metadata in the same folder, with an additional suffix.

        Parameters
        ----------
        suffix : str, default: "_copy"
            See function desc.

        overwrite : bool, default: False
            Wheter to allow the function to overwrite an existing file at `new_path`

        """
        path = self.file_name
        name, ext = os.path.splitext(os.path.basename(path))
        new_path = os.path.join(os.path.dirname(path), name + suffix + ext)
        if os.path.exists(new_path) and not overwrite:
            raise ValueError(
                f"Path already contains a file, use 'overwrite' if you know what you are doing {new_path}"
            )

        return SlfMisc(
            epsg=self.epsg,
            file_name=new_path,
            access="w",
            overwrite=overwrite,
            depth_varname=self.depth_varname,
            x_speed_varname=self.x_speed_varname,
            y_speed_varname=self.y_speed_varname,
            freesurf_varname=self.freesurf_varname,
        )

    def boolean_by_threshold(self, newslf, var: str, threshold: float) -> None:
        """
        Use _boolean_by_threshold, and close the newslf file.
        """
        self._boolean_by_threshold(newslf, var, threshold)
        newslf.close()
        return None

    def _boolean_by_threshold(self, newslf, var: str, threshold: float) -> None:
        """
        In new Slf file, returns 1 if var > thresh, else 0.

        New file only contains this variable, every timesteps are computed.

        Parameters
        ----------
        newslf : Slf
            Selafin file in which to copy the data.

        var : str
            See function desc.

        threshold : float
            See function desc.

        """
        # keep the same mesh
        newslf.read_mesh(self)
        # copy header info
        newslf.add_header(title=self.title, date=self.datetime)

        def __add_variable():
            for variable, unit in zip(
                self.varnames, self.varunits, strict=True
            ):
                if var == variable:
                    newslf.add_variable(var, unit)

        # copying
        ntimesteps = self.get_data_ntimestep()
        for i, timestep in enumerate(range(ntimesteps)):
            time = self.get_data_time(timestep)
            newslf.add_time_step(time)
            #  From TelemacFile.add_variable:
            # "(If no time step in file will create one with time 0.0)"
            # So we need to add times first, then add variables
            if i == 0:
                __add_variable()
            oldvalue = self.get_data_value(var, timestep)
            newvalue = (oldvalue >= threshold).astype(int)
            newslf.add_data_value(var, timestep, newvalue)
        newslf.write()
        return None

    def downsample_by_selection(
        self, newslf, selection: list[int], mode: str = "supr"
    ) -> None:
        """
        Use _downsample_by_selection, and close the newslf file.
        """
        self._downsample_by_selection(newslf, selection, mode)
        newslf.close()
        return None

    def _downsample_by_selection(
        self, newslf, selection: list[int], mode: str = "supr"
    ) -> None:
        """
        Only keep some timesteps from a slf file.

        Parameters
        ----------
        newslf : Slf
            Selafin file in which to copy the data.

        selection : list[int]
            Timestemps to keep.

        mode : str, default: "supr"
            If 'keep', returns a slf file with the same number of records, and data only on those in the selection.
            If 'supr', returns a slf file with only len(selection) records.

        """
        # checking selection is well defined
        ntimesteps = self.get_data_ntimestep()
        for i in selection:
            if i not in range(ntimesteps):
                raise ValueError(f"{i} is not in range({ntimesteps})")
        # keep the same mesh
        newslf.read_mesh(self)
        # copy header info
        newslf.add_header(title=self.title, date=self.datetime)
        #  From TelemacFile.add_variable:
        # "(If no time step in file will create one with time 0.0)"
        # So we need to add times first, then add variables

        def __add_variables():
            for var, unit in zip(self.varnames, self.varunits, strict=True):
                newslf.add_variable(var, unit)

        match mode:
            case "supr":
                # first generate timesteps
                for _, timestep in enumerate(selection):
                    time = self.get_data_time(timestep)
                    newslf.add_time_step(time)
                # then add variables
                __add_variables()
                # then copy data over from self
                for (i, timestep), var in itertools.product(
                    enumerate(selection), self.varnames
                ):
                    value = self.get_data_value(var, timestep)
                    newslf.add_data_value(var, i, value)

            case "keep":
                # since 0 is always included in "keep" mode
                # we can add variables before
                __add_variables()
                # then copy data over from self
                for timestep in range(ntimesteps):
                    time = self.get_data_time(timestep)
                    if time not in newslf.times:
                        newslf.add_time_step(time)
                    if timestep in selection:
                        for var in self.varnames:
                            value = self.get_data_value(var, timestep)
                            newslf.add_data_value(var, timestep, value)

            case _:
                raise ValueError("mode must be either 'keep' or 'supr'")

        newslf.write()
        return None

    def downsample_uniform(
        self, newslf, step_size: int = 5, mode="supr"
    ) -> None:
        """
        Use _downsample_uniform, and close the newslf file.
        """
        self._downsample_uniform(newslf, step_size, mode)
        newslf.close()
        return None

    def _downsample_uniform(
        self, newslf, step_size: int = 5, mode="supr"
    ) -> None:
        """
        Generate an evenly-spaced selection of timesteps to keep from the file.

        Parameters
        ----------
        newslf : Slf
            Selafin file in which to copy the data.

        step_size : int
            The interval between retained timesteps.

        mode : str, default: "supr"
            If 'keep', returns a slf file with the same number of records, and data only on those in the selection.
            If 'supr', returns a slf file with only len(selection) records.

        """
        selection = list(range(0, self.get_data_ntimestep(), step_size))
        self._downsample_by_selection(
            newslf=newslf, selection=selection, mode=mode
        )
        return None

    def variable_subset(self, newslf, vars2keep: list[str]) -> None:
        """
        Use _variable_subset, and close the newslf file.
        """
        self._variable_subset(newslf, vars2keep)
        newslf.close()
        return None

    def _variable_subset(self, newslf, vars2keep: list[str]) -> None:
        """
        Only keep a subset of variables from a given slf file.

        Parameters
        ----------
        newslf : Slf
            Selafin file in which to copy the data.

        vars2keep : list[str]
            Names of variables to keep.

        """
        # keep the same mesh
        newslf.read_mesh(self)
        # copy header info
        newslf.add_header(title=self.title, date=self.datetime)
        # keeping vars in vars2keep
        for var, unit in zip(self.varnames, self.varunits, strict=True):
            if var in vars2keep:
                newslf.add_variable(var, unit)

        # =====================================================================
        # TODO: generate timesteps first, then add variables (like other funcs)
        # =====================================================================

        # interate over the timesteps and the variables to copy the data over
        ntimesteps = self.get_data_ntimestep()
        for i in range(ntimesteps):
            time = self.get_data_time(i)
            newslf.add_time_step(time)
            for var in newslf.varnames:
                value = self.get_data_value(var, i)
                newslf.add_data_value(var, i, value)
        newslf.write()
        return None

    def find_centerline_from_bdtopage(
        self, bdtopagepath: str, topooh: str
    ) -> shapely.LineString:
        """
        Use BDTopage to find the centerline of the simulated river in the slf file.

        Given a BDTopage database that contains shapely.LineStrings
        representing river reaches, generate a new shapely.LineString object
        that represents the centerline of the specified Telemac2D extent

        1. Generates delineation from the selafin file
        2. Read reaches from file within the delineation
        3. Keep those whose 'TopoOH' is @topooh (for example 'la Garonne')
        4. Merges all reaches in a single shapely.LineString

        Parameters
        ----------
        bdtopagepath : str
            Path leading to the BDTopage file.

        topooh : str
            ID of the river, e.g. 'La Garonne'.

        """
        # converting mask to a gpd.GeoSeries to resolve CRS mis-matches when using it as a mask to read file,
        # as per https://geopandas.org/en/v0.14.4/docs/reference/api/geopandas.read_file.html
        mask = gpd.GeoSeries(self.extent, crs=f"EPSG:{self.epsg}")
        # 2.
        reaches = gpd.read_file(bdtopagepath, mask=mask)
        # converting the reaches to the slf epsg
        reaches.to_crs(epsg=self.epsg, inplace=True)
        # 3.
        reaches = reaches[reaches["TopoOH"] == topooh]
        # 4.
        centerline = shapely.line_merge(
            shapely.MultiLineString(reaches["geometry"].to_numpy().tolist())
        )
        return centerline

    def extract_centerline(
        self,
        centerline: shapely.LineString,
        slfvar: str,
    ) -> list[shapely.LineString]:
        """
        Interpolate slf values on a centerline, or any shapely.LineString for that matter.

        For a given shapely.LineString representing a river centerline,
        we interpolate the value of the selafin file on each points used
        to create the shapely.LineString, for every timesteps in the file,
        for a given hydraulic variable

        Returns
        -------
        list[shapely.LineString]
            Coords x and y are a copy of the (x, y) in original centerline, while z contains the interpolated value.

        """
        points = [(x, y) for (x, y, _) in centerline.coords]
        ntimesteps = self.get_data_ntimestep()
        linelist = []

        for timestep in range(ntimesteps):
            values = self.interp_values_on_points(
                varname=slfvar,
                timestep=timestep,
                points=points,
            ).tolist()
            # generating linestring while removing points where no value was interpolated
            linestring = shapely.LineString(
                [
                    (x, y, z)
                    for (x, y), z in zip(points, values, strict=True)
                    if z is not None
                ]
            )
            linelist.append(linestring)

        return linelist

    def save_extent_to_geojson(self, savepath: str) -> None:
        """
        Save the current extent geometry to a GeoJSON file at the specified path.

        Parameters
        ----------
        savepath : str
            See function desc.

        """
        assert savepath.endswith(".geojson")
        (
            gpd.GeoSeries(self.extent)
            .set_crs(epsg=self.epsg)
            .to_file(savepath, driver="GeoJSON")
        )
        return None
