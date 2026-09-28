"""
Spatializes 0D or in-situ data to 2D fields.

defended methods that could be used for estimation:
    - interpolation type fwdet
    - HAND (https://mattbartos.com/pysheds/hand.html).
    -

"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "deprecated",
#     "geopandas",
#     "numpy",
#     "pandas",
#     "pyarrow",
#     "rasterio",
#     "rioxarray",
#     "scipy",
#     "shapely",
#     "tqdm",
#     "xarray",
# ]
# ///
import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray as rxr
import shapely
import xarray as xr
from deprecated import deprecated
from rasterio.enums import Resampling
from scipy.interpolate import RBFInterpolator
from tqdm import tqdm


def index_of_best_match(series: pd.Series, value) -> int:
    """
    Return the integer index of the row whose value is the closest to input value.
    """
    return np.argmin(np.abs(series - value))


@deprecated("Needs refactoring or deleting")
def get_freesurf_hist_from_parquet(
    obs,
    code_station,
    codecol="Code de la station hydrométrique",
    obscol="Résultat de l'observation hydrométrique",
    datecol="Date d'observation hydrométrique",
    refcol="refAlti (m)",
    manual_ref=None,
    obs_scaling=1,
) -> tuple[pd.Series, shapely.Polygon]:
    """
    Extract free-surface elevation history and station geometry from a DataFrame.

    Parameters
    ----------
    obs : pd.DataFrame
        DataFrame containing hydrometric observations.

    code_station : str
        Station code to extract.

    codecol : str
        Column name for station code.

    obscol : str
        Column name for observed value (relative depth).

    datecol : str
        Column name for observation date.

    refcol : str
        Column name for reference altitude.

    manual_ref : float, default: None
        Manual reference altitude if missing in DataFrame.

    obs_scaling : float, default: 1
        Scaling factor for observed values.

    Returns
    -------
    tuple[pd.Series, shapely.Polygon]
        Tuple of (observation history as Series, station geometry as Polygon).

    """

    def __get(col):
        # assumes it is all the same for each station
        return obs[obs[codecol] == code_station][col].to_numpy()[0]
        # if not, then use this
        # res = list(set(obs[obs["Code de la station hydrométrique"] == code_station][col]))
        # assert len(res) == 1, "multiple values for one station"
        # return res[0]

    hist = (
        obs[obs[codecol] == code_station][[datecol, obscol]]
        .set_index(datecol)
        .sort_index()
    )
    # scale obs
    hist[obscol] *= obs_scaling
    # add ref to convert it to free surface
    ref = __get(refcol)
    if np.isnan(ref):
        if manual_ref is None:
            raise ValueError(
                "No reference found, not in df, nor provided by user"
            )
        else:
            ref = manual_ref
    hist[obscol] += ref
    # rename index and col
    hist.index.name = "datetime"
    hist.columns = ["obs"]
    # return also geometry for georeferencing
    return hist, __get("geometry")


@deprecated("Needs refactoring or deleting")
def reindex_hist(
    df_to_reindex: pd.DataFrame,
    start_date: str,
    end_date: str,
    freq: str,
) -> pd.DataFrame:
    """
    Reindex a DataFrame to a fixed date range and interpolate missing values.

    Parameters
    ----------
    df_to_reindex : pd.DataFrame
        DataFrame with datetime index.

    start_date : str
        Start of the date range.

    end_date : str
        End of the date range.

    freq : str
        Frequency string (e.g., '1H').

    Returns
    -------
    pd.DataFrame
        Reindexed and interpolated DataFrame.

    """
    # convert index to datetime objects
    df_to_reindex.index = pd.to_datetime(df_to_reindex.index)
    # create fixed date range to reindex df_to_reindex to
    daterange = pd.date_range(start_date, end_date, freq=freq)
    # remove duplicated points of data before reindexing
    df_to_reindex = df_to_reindex[~df_to_reindex.index.duplicated(keep="first")]
    # reindex + interpolate na values
    return df_to_reindex.reindex(daterange, method="nearest").interpolate()


@deprecated("Needs refactoring or deleting")
def da_from_pt_list(
    pt_list: list | np.ndarray, dem: xr.DataArray
) -> xr.DataArray:
    """
    Generate a DataArray from a list of (x, y, z) points, mapping values to nearest DEM pixels.

    Parameters
    ----------
    pt_list : list | np.ndarray
        List or array of (x, y, z) points.

    dem : xr.DataArray
        Reference DEM with dimensions (band, y, x).

    Returns
    -------
    xr.DataArray
        DataArray with same shape as dem, with point values mapped to nearest pixels.

    """
    # check pt_list format
    pts = np.array(pt_list)
    assert pts.shape[1] == 3, "pt_list should be a list of (x, y, z) points"
    # check epsg
    #
    # check if pts are in dem bbox
    #
    # check if dem is well formated (band, x, y)
    #
    # main loop
    da = dem.copy(data=np.full_like(dem.values, fill_value=np.nan))
    for x, y, z in pt_list:
        nearest_grid_point = da.sel(
            band=1, y=y, x=x, method="nearest"
        ).drop_vars("spatial_ref")
        da.loc[nearest_grid_point.coords] = z
    return da


@deprecated("Needs refactoring or deleting")
def rescale(
    da: xr.DataArray, scale_factor: float | int = 1, method="nearest"
) -> xr.DataArray:
    """
    Rescale a DataArray spatially by a given scale factor and resampling method.

    Parameters
    ----------
    da : xr.DataArray
        DataArray to rescale.

    scale_factor : float | int, default: 1
        Factor to scale width and height.

    method : str, default: "nearest"
        Resampling method ('nearest', 'bilinear', 'average').

    Returns
    -------
    xr.DataArray
        Rescaled DataArray.

    """
    match method:
        case "nearest":
            resampler = Resampling.nearest
        case "bilinear":
            resampler = Resampling.bilinear
        case "average":
            resampler = Resampling.average
        case _:
            raise ValueError("method not in ['nearest', 'bilinear', 'average']")
    w = int(da.rio.width * scale_factor)
    h = int(da.rio.height * scale_factor)
    return da.rio.reproject(da.rio.crs, shape=(h, w), resampling=resampler)


@deprecated("Needs refactoring or deleting")
def rbf_spatialize(da: xr.DataArray) -> xr.DataArray:
    """
    Interpolate missing values in a DataArray using Radial Basis Function (RBF) interpolation.

    Parameters
    ----------
    da : xr.DataArray
        DataArray with missing values to interpolate.

    Returns
    -------
    xr.DataArray
        DataArray with interpolated values.

    """
    mask = da.to_numpy()[0].copy()
    mask[~np.isnan(mask)] = 1
    mask[np.isnan(mask)] = 0
    pts_indexes = np.argwhere(mask)
    freesurf = [
        da.isel(band=0, y=y, x=x).to_numpy().tolist() for y, x in pts_indexes
    ]
    interpolator = RBFInterpolator(
        pts_indexes,
        freesurf,
        neighbors=None,
        smoothing=0.0,
        kernel="linear",
        epsilon=None,
        degree=None,
    )
    xs = np.arange(mask.shape[0])
    ys = np.arange(mask.shape[1])
    grid_pts = np.array([[x, y] for x in xs for y in ys])
    freesurfinterp = interpolator(grid_pts).reshape(mask.shape)
    da.to_numpy()[0] = freesurfinterp
    return da


@deprecated("Needs refactoring or deleting")
def interp_extrap_na(da: xr.DataArray) -> xr.DataArray:
    """
    Interpolate and extrapolate missing values in a DataArray.

    Parameters
    ----------
    da : xr.DataArray
        DataArray with missing values.

    Returns
    -------
    xr.DataArray
        DataArray with interpolated and extrapolated values.

    """
    # interpolate
    da = da.rio.interpolate_na("linear")  # or 'linear'|'cubic'
    # extrapolate
    da = da.rio.interpolate_na("nearest")
    return da


@deprecated("Needs refactoring or deleting")
def get_h_t_from_parquet(
    obs: gpd.GeoDataFrame,
    dem: xr.DataArray,
    stations: list[list[str, float]],
    start_date: str,
    end_date: str,
    freq: str,
    method: str = "rbf",
    obs_scaling: float = 1,
    dem_scaling: float = 1,
) -> tuple[xr.DataArray, xr.DataArray]:
    """
    Compute maximum water depth (H) and flood duration (T) from hydrometric data and DEM.

    Parameters
    ----------
    obs : gpd.GeoDataFrame
        Hydrometric observations with geometry.

    dem : xr.DataArray
        Digital Elevation Model.

    stations : list
        List of [station_code, manual_ref] pairs.

    start_date : str
        Start date for analysis.

    end_date : str
        End date for analysis.

    freq : str
        Frequency string for time steps.

    method : str
        Spatialization method ('rbf' or 'interp').

    obs_scaling : float
        Scaling factor for observations.

    dem_scaling : float
        Scaling factor for DEM.

    Returns
    -------
    tuple[xr.DataArray, xr.DataArray]
        Tuple (H, T) of maximum water depth and flood duration arrays.

    """
    assert dem.rio.crs.to_epsg() == obs.crs.to_epsg(), "not the same epsg"

    # list of [hist, geom]
    hist_geom_list = [
        get_freesurf_hist_from_parquet(
            obs,
            code_station=codeStation,
            manual_ref=manual_ref,
            obs_scaling=obs_scaling,
        )
        for codeStation, manual_ref in stations
    ]

    # reindex [hist, _] to daterange
    hist_geom_list = [
        [
            reindex_hist(
                hist, start_date=start_date, end_date=end_date, freq=freq
            ),
            geom,
        ]
        for hist, geom in hist_geom_list
    ]

    daterange = pd.date_range(start_date, end_date, freq=freq)

    xs = [geom.x for _, geom in hist_geom_list]
    ys = [geom.y for _, geom in hist_geom_list]

    rescaled_dem = rescale(dem, dem_scaling)

    water_depths = []

    match method:
        case "rbf":
            spatializator = rbf_spatialize
        case "interp":
            spatializator = interp_extrap_na

    for date in daterange:
        zs = [hist.loc[date, "obs"] for hist, _ in hist_geom_list]
        pt_list = [(x, y, z) for x, y, z in zip(xs, ys, zs, strict=True)]
        fsf = da_from_pt_list(pt_list, rescaled_dem)
        fsf = spatializator(fsf)
        water_depth = fsf.where(rescaled_dem) - rescaled_dem
        water_depth = water_depth.where(water_depth >= 0, other=np.nan)
        water_depths.append(water_depth)

    # Stack all water_depths into a single DataArray with a new 'time' dimension
    water_depth_da = xr.concat(
        water_depths, dim=pd.Index(daterange, name="time")
    )

    # to get h, take the max
    h = water_depth_da.max(dim="time")

    # flooded if depth > 0
    flooded_timesteps = (water_depth_da > 0).sum(dim="time")

    # Get the duration of one timestep in seconds
    timestep_seconds = pd.Timedelta(freq).total_seconds()

    # Compute total flooded time in seconds for each pixel
    t = flooded_timesteps * timestep_seconds

    return h, t


def get_spatialized_obs_at_date(
    obs: gpd.GeoDataFrame,
    dem: xr.DataArray,
    stations: list[str],
    refs: list[float],
    target_date: str | pd.Timestamp,
    interp_method: str = "rbf",
):
    """
    ...

    For construction of the geoparquet, see exps/in_situ_hydroportail.py

    Parameters
    ----------
    obs : gpd.GeoDataFrame
        See exps/in_situ_hydroportail.py

    dem : xr.DataArray
        Digital Elevation Model

    stations : list[str]
        Station codes corresponding to col 'Code de la station hydrométrique' of obs.

    refs : list[float]
        Manual adjustment in meters of the observation value, for each station.

    target_date : str | pd.Timestamp
        Wished observation date, will return the closest date for each station (dates can differ between stations).

    interp_method : "iena" | "rbf"
        "iena" : Interpolate Extrapolate NA
        "rbf" : Radial Basis Function

    Returns
    -------
    xr.DataArray
        With same shape and metadata as the input DEM.

    """
    # Read corresponding records for each station at the closest available date
    records = []
    for station in stations:
        local_obs = obs[obs["Code de la station hydrométrique"] == station]
        assert len(local_obs) != 0, "Station id returned no data."
        i = index_of_best_match(
            pd.to_datetime(local_obs["Date d'observation hydrométrique"]),
            pd.to_datetime(target_date),
        )
        records.append(local_obs.iloc[i])

    # Format everything in a x,y,z list
    xyzs = [
        [
            record["geometry"].x,
            record["geometry"].y,
            # Divide by 1000 because hydroportail give obs in mm, ref is in meters
            (record["Résultat de l'observation hydrométrique"] / 1000) + ref,
        ]
        for record, ref in zip(records, refs, strict=True)
    ]

    # Interp freesurface
    match interp_method:
        case "iena":
            spatfunc = interp_extrap_na
        case "ina":

            def spatfunc(x):
                return x.rio.interpolate_na("linear")
        case "rbf":
            spatfunc = rbf_spatialize
        case _:
            raise ValueError()
    freesurf = spatfunc(da_from_pt_list(xyzs, dem=dem))

    # Return depth
    depth = freesurf.where(dem) - dem
    return depth.where(depth >= 0)


if __name__ == "__main__":
    dem = rxr.open_rasterio(
        "/archive/globc/garin/TMP/stomerGLOBAL/dem/dem_stomerGLOBAL.tif"
    )

    obspath = "/archive/globc/garin/INP/hdf2324/ins/ObsHDF2324.parquet"
    aoipath = "/archive/globc/garin/INP/hdf2324/aoi/Perimetre_SmageAa.shp"

    buffsize = 0

    aoi = gpd.read_file(aoipath)
    obs = gpd.read_parquet(obspath).clip(aoi.buffer(buffsize))

    obs.to_parquet(
        "/archive/globc/garin/INP/hdf2324/ins/ObsHDF2324_AOI.parquet"
    )
    obs.to_file("/archive/globc/garin/INP/hdf2324/ins/ObsHDF2324_AOI.shp")
    import sys

    sys.exit()

    available_stations = np.unique(obs["Code de la station hydrométrique"])

    stations = [
        "E403000101",  # Arques
        "E403571003",  # Wizernes
        "E403572001",
        "E403653001",
        "E403653301",
        "E403653401",  # Blendecques
    ]

    refs = [
        obs[obs["Code de la station hydrométrique"] == station][
            "refAlti (m)"
        ].iloc[0]
        for station in stations
    ]

    # removing where there is no refAlti (m)
    stations = stations[1:-1]
    refs = refs[1:-1]

    outdir = "/archive/globc/garin/OUT"

    for date in tqdm(pd.date_range("2023-10-01", "2024-01-31", freq="1W")):
        for method in ["ina", "iena", "rbf"]:
            da = get_spatialized_obs_at_date(
                obs=obs,
                dem=dem,
                stations=stations,
                refs=refs,
                target_date=date,
                interp_method=method,
            )
            da.rio.to_raster(f"{outdir}/spat0D-{date}-{method}.tif")

    da1 = rxr.open_rasterio(f"{outdir}/spat0D-2023-10-01 00:00:00-iena.tif")
    da2 = rxr.open_rasterio(f"{outdir}/spat0D-2023-11-12 00:00:00-iena.tif")
