# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "geopandas",
#     "openeo",
# ]
# ///
import geopandas as gpd
import openeo

connection = openeo.connect("https://openeo.dataspace.copernicus.eu/openeo/1.2")

connection.authenticate_oidc()

extents = {
    # "marmande": "/archive2/globc/seiche/marmande_2019_inp/marmande_aoi.geojson",
    # "stomer": "/archive2/globc/seiche/stomer_inp/Perimetre_SmageAa.shp",
    "ohio": "/archive2/globc/seiche/ohio_2025_inp/ohio.geojson",
}

for name, file in extents.items():
    w, s, e, n = gpd.read_file(file).to_crs(epsg=4326).total_bounds

    for collection in [
        "COPERNICUS_30",
        "ESA_WORLDCOVER_10M_2020_V1",
        "ESA_WORLDCOVER_10M_2021_V2",
    ]:
        print(f"\n{name} - {collection}\n")
        datacube = connection.load_collection(
            collection,
            spatial_extent={
                "west": w,
                "south": s,
                "east": e,
                "north": n,
            },
        )

        job = datacube.create_job(out_format="GTiff")

        job.start_and_wait()

        results = job.get_results()

        results.download_files(
            f"/archive2/globc/seiche/_other/{collection}_{name}"
        )
