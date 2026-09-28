# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "geopandas",
#     "pygeodes",
# ]
# ///
import geopandas as gpd
import pygeodes

# works with .pygeodes-config.json in cwd
conf = pygeodes.Config.from_file()

geodes = pygeodes.Geodes(conf=conf)

file = "/archive2/globc/seiche/marmande_2019_inp/marmande_aoi.geojson"

# bbox is a bit useless since the raster covers all mainland france
# but otherwise the api screams if we dont put it
bbox = gpd.read_file(file).to_crs(epsg=4326).total_bounds

items, df = geodes.search_items(
    collections=["THEIA_OSO_RASTER_L3B"], bbox=bbox.tolist()
)

for item in items:
    okaykeys = [
        "OSO_20180101_RASTER",
        # "OSO_20190101_RASTER",
        # "OSO_20210101_RASTER",
        # "OSO_20220101_RASTER",
        # "OSO_20230101_RASTER",
    ]
    if any([key in item.s3_path for key in okaykeys]):
        geodes.download_item_archive(item)
