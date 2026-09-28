"""
Preprocess Sentinel-2 snow (SNW) and cloud (CLD) cover bands.

Three steps, run as subcommands:

    uv run --script tools/filter_s2.py download --aoi aoi.shp --start 2023-10-01 --end 2024-01-31 --outdir raw/
    uv run --script tools/filter_s2.py format --aoi aoi.shp --raw-dir raw/ --out snwcld.nc
    uv run --script tools/filter_s2.py mask-bfm --aoi aoi.shp --snwcld snwcld.nc --bfm-dir S2/ --outdir masked/

- ``download`` fetches the SNW/CLD bands on the AOI bbox via the OpenEO API
  (interactive OIDC authentication).
- ``format`` reprojects and clips the downloaded GTiffs into one netCDF.
- ``mask-bfm`` zeroes out BFM pixels whose SNW/CLD band exceeds the thresholds.
"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "geopandas",
#     "openeo",
#     "pandas",
#     "rioxarray",
#     "tqdm",
#     "xarray",
# ]
# ///
import argparse
import glob
import os
import re

import geopandas as gpd
import pandas as pd
import rioxarray as rxr
import xarray as xr


def reproj_clip(
    da: xr.DataArray,
    epsg: int,
    poly: gpd.GeoDataFrame,
    *,
    pad: bool = True,
) -> xr.DataArray | None:
    """
    Clip and reproject a DataArray to a polygon's bounding box and EPSG code.

    Vendored from seiche.utils_da so this script stays standalone; keep the
    two copies in sync.

    Parameters
    ----------
    da : xr.DataArray
        Input DataArray to be clipped and reprojected.
    epsg : int
        EPSG code for target projection.
    poly : gpd.GeoDataFrame
        Polygon(s) for clipping and reprojection.
    pad : bool
        Whether or not to pad the clipped data to the full extent of ``poly``.

    Returns
    -------
    xr.DataArray | None
        Clipped and reprojected DataArray, or ``None`` if no data is in bounds.

    """
    clipper = poly.to_crs(epsg=da.rio.crs.to_epsg())
    try:
        newda = (
            da.rio.clip_box(*clipper.total_bounds)
            .rio.clip(clipper.geometry.values)
            .rio.reproject(f"EPSG:{epsg}")
        )
    except rxr.exceptions.NoDataInBounds:
        return None
    if pad:
        newda = newda.rio.pad_xy(*poly.total_bounds)
    return newda


def download_snow_cloud_cover(
    aoi_path: str,
    start: str,
    end: str,
    outdir: str,
) -> None:
    """
    Download S2 SNW and CLD bands on a given bbox and time range via OpenEO.

    Parameters
    ----------
    aoi_path : str
        Path to the AOI vector file.
    start : str
        Start of the temporal extent, e.g. "2023-10-01".
    end : str
        End of the temporal extent, e.g. "2024-01-31".
    outdir : str
        Directory where the GTiffs are downloaded.

    """
    import openeo

    aoi = gpd.read_file(aoi_path)
    west, south, east, north = aoi.to_crs(epsg="4326").total_bounds
    connection = openeo.connect(
        "https://openeo.dataspace.copernicus.eu/openeo/1.2"
    )
    connection.authenticate_oidc()
    datacube = connection.load_collection(
        "SENTINEL2_L2A",
        spatial_extent={
            "west": float(west),
            "south": float(south),
            "east": float(east),
            "north": float(north),
        },
        temporal_extent=[start, end],
        bands=["SNW", "CLD"],
    )
    job = datacube.create_job(out_format="GTiff")
    job.start_and_wait()
    results = job.get_results()
    results.download_files(outdir)


def format_snow_cloud_cover(
    raw_dir: str,
    aoi_path: str,
    out_path: str,
    epsg: int = 2154,
) -> None:
    """
    Format downloaded S2 SNW/CLD GTiffs into a single time-sorted netCDF.

    Parameters
    ----------
    raw_dir : str
        Directory containing the raw GTiffs.
    aoi_path : str
        Path to the AOI vector file.
    out_path : str
        Destination netCDF file.
    epsg : int
        EPSG code to reproject to. Default 2154.

    """
    from tqdm import tqdm

    aoi = gpd.read_file(aoi_path)
    paths = glob.glob(os.path.join(raw_dir, "*.tif"))

    def rasters(paths: list[str]):
        for path in tqdm(paths, desc="reproj_clip SNW CLD", unit=" image"):
            date = pd.to_datetime(
                re.search(r"(\d{4})-(\d{2})-(\d{2})", os.path.basename(path)).group()
            )
            da = reproj_clip(
                rxr.open_rasterio(path, chunks="auto"), epsg=epsg, poly=aoi
            )
            # reproj_clip returns None when no data is in bounds
            if da is not None:
                yield da.assign_coords(time=date).expand_dims(dim="time")

    xr.concat(rasters(paths), dim="time").sortby("time").to_netcdf(out_path)


def remove_snow_cloud_from_s2_bfm(
    snwcld_path: str,
    bfm_dir: str,
    aoi_path: str,
    savedir: str,
    epsg: int = 2154,
    snwthresh: int = 50,
    cldthresh: int = 50,
) -> None:
    """
    Generate the snow- and cloud-free version of the BFM raster dataset.

    BFM pixels whose SNW or CLD band exceeds the thresholds are set to nodata.

    Parameters
    ----------
    snwcld_path : str
        Path to the SNW/CLD netCDF produced by ``format_snow_cloud_cover``.
    bfm_dir : str
        Directory (searched recursively) containing the BFM rasters.
    aoi_path : str
        Path to the AOI vector file.
    savedir : str
        Directory where the masked BFM rasters are written.
    epsg : int
        EPSG code to reproject to. Default 2154.
    snwthresh : int
        Maximum allowed snow cover percentage. Default 50.
    cldthresh : int
        Maximum allowed cloud cover percentage. Default 50.

    """
    from tqdm import tqdm

    aoi = gpd.read_file(aoi_path)
    os.makedirs(savedir, exist_ok=True)
    snwcld = xr.open_dataset(snwcld_path, decode_coords="all")[
        "__xarray_dataarray_variable__"
    ]

    for path in tqdm(
        glob.glob(os.path.join(bfm_dir, "**", "*POST.tif"), recursive=True),
        desc="Removing cloud and snow",
        unit=" raster",
    ):
        time = (
            pd.to_datetime(re.search(r"(\d{8})T(\d{6})", path).group())
            .floor(freq="1D")  # openEO dates have no hours, minutes, seconds
            .to_datetime64()
        )
        snwcld_at_time = snwcld.sel(time=time)
        snw_at_time = snwcld_at_time.isel(band=0).fillna(0)
        cld_at_time = snwcld_at_time.isel(band=1).fillna(0)
        bfm_at_time = reproj_clip(
            rxr.open_rasterio(path, chunks="auto"), epsg=epsg, poly=aoi
        )
        if bfm_at_time is not None:
            bfm_at_time.where(
                (cld_at_time <= cldthresh) & (snw_at_time <= snwthresh),
                other=bfm_at_time.rio.nodata,
            ).rio.to_raster(
                os.path.join(
                    savedir,
                    f"{os.path.basename(path)[:-4]}_SNW_CLD_under_{snwthresh}.tif",
                )
            )


def main(args: list[str] | None = None) -> None:
    """
    CLI entrypoint: download, format, or mask S2 SNW/CLD data.
    """
    parser = argparse.ArgumentParser(
        prog="filter_s2.py",
        description="Preprocess Sentinel-2 snow (SNW) and cloud (CLD) cover data.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_download = subparsers.add_parser(
        "download", help="download S2 SNW/CLD bands via OpenEO"
    )
    p_download.add_argument("--aoi", required=True, help="path to the AOI vector file")
    p_download.add_argument("--start", required=True, help="start date, e.g. 2023-10-01")
    p_download.add_argument("--end", required=True, help="end date, e.g. 2024-01-31")
    p_download.add_argument(
        "--outdir", required=True, help="directory for the downloaded GTiffs"
    )

    p_format = subparsers.add_parser(
        "format", help="reproject/clip the raw GTiffs into a single netCDF"
    )
    p_format.add_argument(
        "--raw-dir", required=True, help="directory of the raw GTiffs"
    )
    p_format.add_argument("--aoi", required=True, help="path to the AOI vector file")
    p_format.add_argument("--out", required=True, help="destination netCDF path")
    p_format.add_argument(
        "--epsg", type=int, default=2154, help="target EPSG (default: 2154)"
    )

    p_mask = subparsers.add_parser(
        "mask-bfm", help="mask BFM rasters where SNW/CLD exceed the thresholds"
    )
    p_mask.add_argument(
        "--snwcld", required=True, help="SNW/CLD netCDF from the format command"
    )
    p_mask.add_argument(
        "--bfm-dir", required=True, help="directory (recursive) of the BFM rasters"
    )
    p_mask.add_argument("--aoi", required=True, help="path to the AOI vector file")
    p_mask.add_argument(
        "--outdir", required=True, help="directory for the masked rasters"
    )
    p_mask.add_argument(
        "--epsg", type=int, default=2154, help="target EPSG (default: 2154)"
    )
    p_mask.add_argument(
        "--snw-thresh", type=int, default=50, help="max snow % (default: 50)"
    )
    p_mask.add_argument(
        "--cld-thresh", type=int, default=50, help="max cloud % (default: 50)"
    )

    args = parser.parse_args(args)

    if args.command == "download":
        download_snow_cloud_cover(args.aoi, args.start, args.end, args.outdir)
    elif args.command == "format":
        format_snow_cloud_cover(args.raw_dir, args.aoi, args.out, args.epsg)
    elif args.command == "mask-bfm":
        remove_snow_cloud_from_s2_bfm(
            args.snwcld,
            args.bfm_dir,
            args.aoi,
            args.outdir,
            args.epsg,
            args.snw_thresh,
            args.cld_thresh,
        )


if __name__ == "__main__":
    main()
