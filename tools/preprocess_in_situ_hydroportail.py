"""
Preprocess in-situ Hydroportail observations into a geoparquet.

Run with:
    uv run --script tools/preprocess_in_situ_hydroportail.py
"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "bs4",
#     "contextily",
#     "geopandas",
#     "matplotlib",
#     "numpy",
#     "pandas",
#     "requests",
#     "shapely",
#     "tqdm",
#     "pyyaml",
# ]
# ///
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from datetime import datetime
from tqdm import tqdm
import re
import yaml
import requests
from bs4 import BeautifulSoup
import shapely
import contextily as cx


def createRawDF(dfpath) -> pd.DataFrame:
    # read and put in list
    csvs = []
    for i in range(1, 12):
        if i != 1:
            path = os.path.join(DATADIR, f"export_hydro_series {i}.csv")
        else:
            path = os.path.join(DATADIR, "export_hydro_series.csv")
        # skip first row and skip last col
        csvs.append(
            pd.read_csv(path, sep=";", skiprows=1, usecols=list(range(10)))
        )
    # merge into one csv
    df = pd.concat(csvs, axis=0, ignore_index=True)
    df.to_csv(dfpath)
    return df


def scrapeHTMLStationInfo(codeStation: str) -> None:
    # https://realpython.com/beautiful-soup-web-scraper-python/
    # nasty but works
    replaceDict = {
        "\n": "",
        '<div class="identity__field"><span class="identity__label">': "",
        "</span><span>": ":",
        "</span></div>": "",
        '<div class="identity__field"></div>': "",
        '<div class="identity__field full-width"><span class="identity__label">': "",
        "<ul><li>": "\n  - ",
        "</li><li>": "\n  - ",
        "</li></ul>": "",
        "<br/>": "",
        "[": "(",
        "]": ")",
        "Date de mise à jour de la référence altimétrique.:": "Date de mise à jour de la référence altimétrique: ",
        "Finalité(s):": "Finalité(s): ",
        "Date de la dernière mise à jour:": "Date de la dernière mise à jour: ",
        "Date de mise en service:": "Date de mise en service: ",
        "Latitude :": "\n  - Latitude:",
        "Longitude :": "\n  - Longitude:",
        "Basses eaux :": "\n  - Basses eaux:",
        "Moyennes eaux :": "\n  - Moyennes eaux:",
        "Hautes eaux :": "\n  - Hautes eaux:",
        "Vigicrues :": "\n  - Vigicrues:",
        "Supervision :": "\n  - Supervision:",
        "Date de mise hors service:": "Date de mise hors service: ",
        "- Fermée ": "Fermée",
        " : ": " ",  # be careful with this one
        # '.':'',
    }
    url = f"https://www.hydro.eaufrance.fr/stationhydro/{codeStation}/fiche"
    filepath = os.path.join(
        DATADIR, f"./htmlScrapedStationInfo/{codeStation}.yml"
    )

    try:  # try to see if file exists / config is parseable
        with open(filepath, "r") as file:
            config = yaml.safe_load(file)
    except:  # otherwise redownload and reformat
        print(filepath)

        # https://stackoverflow.com/questions/38489386/how-to-fix-403-forbidden-errors-when-calling-apis-using-python-requests
        page = requests.get(
            url=url,
            headers={"User-Agent": "Mozilla/5.0"},  # to avoid response 403
        )

        match page.status_code:
            case 200:  # ok response
                soup = BeautifulSoup(page.content, "html.parser")
                job_cards = soup.find_all("div", class_="identity__field")
                with open(filepath, "w") as f:
                    f.write(
                        f"""# info gathered automatically by scraping <div class="identity__field">
# of {url}
# on {datetime.now()}

"""
                    )
                    for j in job_cards:
                        s = str(j)
                        for k, v in replaceDict.items():
                            s = s.replace(k, v)
                        s = re.sub(
                            r"<.*?>", "", s
                        )  # remove <timedatetime> markups
                        s = " ".join(
                            re.split(" +", s)
                        )  # remove multiple spaces
                        f.write(s)
                        f.write("\n")
                # time.sleep(1)

            case _:
                print(codeStation, "\t", page.status_code)
                raise ValueError()


def createMetaDF(dfpath) -> pd.DataFrame:
    d = dict()
    d["refAlti (m)"] = dict()
    d["coords"] = dict()
    d["epsg"] = dict()

    codeStations = np.unique(rawdf["Code de la station hydrométrique"]).tolist()
    for codeStation in codeStations:
        filepath = os.path.join(
            DATADIR, f"./htmlScrapedStationInfo/{codeStation}.yml"
        )
        with open(filepath, "r") as file:
            config = yaml.safe_load(file)

        # refAlti
        match codeStation:
            # manual corrections based on 'Commentaire'
            case "E635142601":
                refAlti = 37.783  # m, IGN1969
            case "E635142602":
                refAlti = 37.779  # m, IGN1969
            case _:
                refAlti = config["Cote du zéro d'échelle"]

                if refAlti == "Non renseigné(e)":
                    refAlti = np.nan
                else:
                    refAlti = float(
                        refAlti.replace("\u202f", ".")
                        .replace(" ", "")
                        .replace(",", ".")
                        .replace("m", "")
                    )

        # geometry
        lat, lon = (
            config["Coordonnées"][0]["Latitude"],
            config["Coordonnées"][1]["Longitude"],
        )
        lat = float(lat.replace("\u202f", "").replace(",", "."))
        lon = float(lon.replace("\u202f", "").replace(",", "."))
        coords = shapely.Point(lon, lat)

        # epsg
        epsg = int(
            config["Type de projection"]
            .replace("Lambert 93 (EPSG:2154)", "2154")
            .replace("Lambert II étendu (EPSG:27582)", "27582")
        )

        d["refAlti (m)"][codeStation] = refAlti
        d["coords"][codeStation] = coords
        d["epsg"][codeStation] = epsg

    metadf = pd.DataFrame.from_dict(d)
    metadf.to_csv(dfpath)
    return metadf


if __name__ == "__main__":
    DATADIR = "/archive/globc/garin/INP/hdf2324/ins"
    RAWDFPATH = os.path.join(DATADIR, "rawObsHDF2324.csv")
    METADFPATH = os.path.join(DATADIR, "metaHDF2324.csv")
    FINAL_PATH = os.path.join(DATADIR, "ObsHDF2324.parquet")

    if not os.path.exists(FINAL_PATH):
        # merge csvs into one
        if not os.path.exists(RAWDFPATH):
            print("Creating rawdf...")
            rawdf = createRawDF(RAWDFPATH)
        else:
            print("rawdf already exists, reading rawdf...")
            rawdf = pd.read_csv(RAWDFPATH, index_col=0)

        # download metadata from website to yml files
        codeStations = np.unique(
            rawdf["Code de la station hydrométrique"]
        ).tolist()
        print("Scraping metadata from website...")
        for codeStation in tqdm(codeStations):
            # will skip if config already exists and is parseable
            scrapeHTMLStationInfo(codeStation)

        # get metadata from yml and put in metadf
        if not os.path.exists(METADFPATH):
            print("Creating metadf...")
            metadf = createMetaDF(METADFPATH)
        else:
            print("metadf already exists, reading metadf...")
            metadf = pd.read_csv(METADFPATH, index_col=0)

        # merge df and create gdf
        df = rawdf.join(metadf, on="Code de la station hydrométrique")
        # in this specific case, only 2154 and 27582
        assert len(np.unique(df["epsg"])) == 2
        assert 2154 in np.unique(df["epsg"])
        assert 27582 in np.unique(df["epsg"])

        gdf2154 = gpd.GeoDataFrame(df[df["epsg"] == 2154])
        print("Creating gdf2154...")
        gdf2154["coords"] = [
            shapely.from_wkt(pt) for pt in tqdm(gdf2154["coords"])
        ]
        gdf2154 = gdf2154.set_geometry("coords", drop=True).set_crs(epsg=2154)

        gdf27582 = gpd.GeoDataFrame(df[df["epsg"] == 27582])
        print("Creating gdf27582...")
        gdf27582["coords"] = [
            shapely.from_wkt(pt) for pt in tqdm(gdf27582["coords"])
        ]
        gdf27582 = gdf27582.set_geometry("coords", drop=True).set_crs(
            epsg=27582
        )

        gdf = pd.concat([gdf2154, gdf27582.to_crs(epsg=2154)], axis=0).drop(
            "epsg", axis=1
        )

        print("Saving to file...")
        gdf.to_parquet(FINAL_PATH)
        print("Done!")
    else:
        print("ObsHDF2324 already exists, reading ObsHDF2324...")
        gdf = gpd.read_parquet(FINAL_PATH)
        print("Plotting stations...")
        u = gpd.GeoSeries(gdf.geometry.unique())
        ax = u.plot()
        cx.add_basemap(ax, crs=u.crs, attribution_size=0)
        plt.title("Stations hdf2324")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.savefig("stations.png", bbox_inches="tight", dpi=300)
