"""
Precompile the raw Floodam Excel files into netCDF/CSV that dmgfunc_floodam reads.

Run with:
    uv run --script tools/format_floodam.py

Outputs are written to data/floodam/precompiled/ along with a sha256.txt manifest
used by dmgfunc_floodam to detect corrupted files.
"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "h5netcdf",
#     "h5py",
#     "numpy",
#     "openpyxl",
#     "pandas",
#     "requests",
#     "xarray",
#     "xlrd",
#     "bs4",
#     "tqdm",
# ]
# ///
import hashlib
import json
import os
import time
import zipfile

import numpy as np
import pandas as pd
import requests
import xarray as xr
from bs4 import BeautifulSoup
from tqdm import tqdm

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "floodam")
OUT_DIR = os.path.join(DATA_DIR, "precompiled")

# expected sha256 of the raw excel files
SHA256CHECKSUMS = {
    "ct.xls": "74fe542b249fc9b45af7fb26b1d844e9945e4c44b5a47cfecf172bf38318d26b",
    "fa.xls": "384a80e5b3b3b912bf653f22f04fd417dcfe5579fc3d2cb9cf223b3a50f76591",
    "fc.xlsx": "3c9a34e8393cef4124107e04d32524fdcc4193bb957a97291be1b096783b0329",
    "fh.xls": "eb4ee04f27aefe387acc59f3a2f3eac0791697904054db2b77eac1656b713aaf",
    "fp.xls": "655be159facc4055bd010ed85a623d040472c4febfb70d87fd5038580e45b32f",
    "fw.xlsx": "832b81bd08ba4c8f6d98e3fccb8026e81755f5af78ba32ad7da962a9707c81d4",
    "mc.xlsx": "3c9a34e8393cef4124107e04d32524fdcc4193bb957a97291be1b096783b0329",
    "mh.xls": "f09c8f38e331f728aa037af12654abd17a66920bc6c53f45f47dd76d826e0bee",
    "mp.xls": "e40c4538659bac9ef276719100c1dd5579c94f12c7007b258f3a719f3efff996",
}


def _get_all_links(url):
    """
    Return all href links found on a page.
    """
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        return [a["href"] for a in soup.find_all("a", href=True)]
    print(f"Failed to retrieve the page. Status code: {response.status_code}")
    return []


# > last tested : 2025-01-30
def download_xls_files(
    datadir: str,
    url: str = "https://www.ecologie.gouv.fr/politiques-publiques/levaluation-economique-projets-gestion-risques-naturels",
) -> None:
    """
    Download and rename Floodam Excel files.
    """
    all_links = _get_all_links(url)
    links = [
        link for link in all_links if "fonction" in link or "Fonction" in link
    ]

    # renaming dict
    replace_dict = {
        # fw (fluvial waste waters)
        "AMC%20-%20Fonctions%20de%20dommages%20fluvial%20stations%20de%20traitement%20des%20us%C3%A9es": "fw",
        # fh (fluvial housing)
        "AMC%20-%20Fonctions%20de%20dommages%20fluvial%20logements": "fh",
        # fp (fluvial public)
        "AMC%20-%20Fonctions%20de%20dommages%20fluvial%20%C3%A9tablissements%20publics": "fp",
        # fc (fluvial commercial)
        "AMC%20-%20Fonctions%20de%20dommages%20fluvial%20submersions%20entreprises": "fc",
        # fa (fluvial agriculture)
        "AMC%20-%20Fonctions%20de%20dommages%20fluvial%20agriculture": "fa",
        # ct (correspondance table)
        "AMC%20-%20Tableau%20de%20correspondance%20%20fonctions%20de%20dommages%20entreprises%20et%20%C3%A9tablissements%20publics%20": "ct",
        # mc (maritime commercial)
        "AMC%20-%20Fonctions%20de%20dommages%20fluvial%20submersions%20marines%20entreprises": "mc",
        # mh (maritime housing)
        "AMC%20-%20Fonctions%20de%20dommages%20submersions%20marines%20logement": "mh",
        # mp (maritime public)
        "AMC%20-%20Fonctions%20de%20dommages%20submersions%20marines%20%C3%A9tablissements%20publics": "mp",
    }

    # downloading and storing files
    for link in links:
        filename, extension = os.path.splitext(link)
        filename = replace_dict[os.path.basename(filename)]
        print(f"Downloading: {filename}")
        response = requests.get(link, stream=True)
        path = os.path.join(datadir, f"{filename}{extension}")
        with open(path, "wb") as handle:
            for data in tqdm(response.iter_content(chunk_size=1024), unit="kB"):
                handle.write(data)

        # extract and rename zip
        if extension == ".zip":
            with zipfile.ZipFile(path, "r") as z:
                assert len(z.namelist()) == 1, "more than one file in archive"
                extracted_name = z.namelist()[0]
                z.extractall(datadir)
                os.rename(
                    os.path.join(datadir, extracted_name),
                    os.path.join(datadir, f"{filename}.xlsx"),
                )
                os.remove(path)

        # sleep to not get kicked by server
        time.sleep(1)

    return None


def format_a(path) -> xr.Dataset:
    """
    Get formatted agriculture damage functions from Floodam Excel file.
    """
    df_agri = pd.read_excel(path, header=[1], sheet_name=0)
    replace_dict = {
        "Hauteur d'eau min (cm)": "hmin",
        "Hauteur d'eau max (cm)": "hmax",
        "Vitesse du courant": "maxSpeed",
        "Durée de submersion": "duration",
        "Saison": "season",
        "Blé tendre": "wheat",
        "Mais grain et ensilage": "corn",
        "Orge": "barley",
        "Autres céréales": "otherCereals",
        "Colza": "colza",
        "Tournesol": "sunflower",
        "Autres oléagineux": "otherOleaginous",
        "Autres cultures industrielles": "otherIndustrial",
        "Arboriculture et vergers": "orchard",
        "Vignes": "grapevine",
        "Légumes-fleurs": "flowerVegetables",
        "Fourrage": "fodder",
        "Prairies permanentes": "permanentGrasslands",
        "Prairies temporaires": "temporaryGrasslands",
    }
    
    df_agri.columns = np.vectorize(replace_dict.get)(df_agri.columns)
    # only keep max depth as the mean of the interval
    # if step function, then just use a nearest neighboor interpolator
    df_agri["maxDepth"] = (df_agri["hmin"] + df_agri["hmax"]) / 2
    # drop inf rows because inf maxDepth is not possible
    # (damage is equivalent so doesnt change much)
    # + np.interp already handles extrapolation
    df_agri = df_agri[df_agri["maxDepth"] != np.inf]
    # drop some columns
    df_agri = df_agri.drop(["hmin", "hmax"], axis=1)
    # convertm maxDepth from cm to m
    df_agri["maxDepth"] /= 100
    # there is one mistake where it is written "moyn" instead of "moyen" in the maxSpeed col
    df_agri["maxSpeed"] = df_agri["maxSpeed"].replace("moyn", "moyen")
    # ---
    # convert from qualitative to ranges that
    # can be used for nearest neighboor interpolation
    # see Tableau 8 and Tableau 9 of Guide méthodologique 2018 for floodam
    # see Methods/Floodam in the documentation website for more details
    df_agri["maxSpeed"] = (
        df_agri["maxSpeed"]
        .replace(
            {
                "faible": 0.25,  # 0 -> 0.5 m/s
                "moyen": 0.75,  # 0.5 -> 1 m/s
                "fort": 1.5,  # 1 -> 2 m/s
            }
        )
        .infer_objects()
    )
    df_agri["duration"] = (
        df_agri["duration"]
        .replace(
            {
                # courte: 0 -> 1 day
                # moyenne: 2 -> 4 days
                # longue: 5 -> 10 days
                # très longue: 11 -> 20 days
                #
                # for continuity, ranges become:
                #
                # courte: 0 -> 1.5 days         : 0 -> 36h
                # moyenne: 1.5 -> 4.5 days      : 36h -> 108h
                # longue: 4.5 -> 10.5 days      : 108h -> 252h
                # très longue: 10.5 -> 20 days  : 252 -> 480h
                #
                # then we take the mean for each range for nearest neighboor interpolation
                #
                "courte": 64_800,  # 18h = 64_800s
                "moyenne": 259_200,  # 72h = 259_200s
                "longue": 648_000,  # 180h = 648_000s
                "très longue": 1_317_600,  # 366h = 1_317_600s
            }
        )
        .infer_objects()
    )
    # ---
    # set dmgfunc inputs as index
    df_agri = df_agri.set_index(["maxDepth", "maxSpeed", "duration", "season"])
    # convert from €2016/ha to €2016/m2
    df_agri /= 10_000
    # put in xr.Dataset after putting dmgfunc inputs as index
    ds = df_agri.to_xarray()
    # units
    ds.attrs["units"] = {
        "dmg": "€2016/m2",
        "maxDepth": "m",
        "maxSpeed": "m/s",
        "duration": "s",
        "season": "qualitative",
    }
    ds.attrs["name"] = "a"
    ds.attrs["alea"] = "fluvial"
    return ds


def format_h(path) -> xr.Dataset:
    """
    Get formatted housing damage functions from Floodam Excel file.
    """
    df_housing = pd.read_excel(path, header=[0, 1], sheet_name=0)
    df_housing.columns = pd.Index(
        [
            "hmin",
            "hmax",
            "duration",
            "bise",  # bati, individuel sans etage
            "biae",  # bati, individuel avec etage
            "bcol",  # bati, collectif
            "ssi",  # bati, sous sol individuel
            "ssc",  # bati, sous sol collectif
            "mise",  # mobilier, individuel sans etage
            "miae",  # mobilier, individuel avec etage
            "mcol",  # mobilier, collectif
        ]
    )
    # add bâti and mobilier classes e.g.: ise = bise + mise
    df_housing["ise"] = df_housing["bise"] + df_housing["mise"]
    df_housing["iae"] = df_housing["biae"] + df_housing["miae"]
    df_housing["col"] = df_housing["bcol"] + df_housing["mcol"]
    df_housing = df_housing.drop(
        ["bise", "biae", "bcol", "mise", "miae", "mcol"],
        axis=1,
    )
    # format duration
    df_housing["duration"] = [
        24 if duration == "<48h" else 72 for duration in df_housing["duration"]
    ]
    # only keep max depth as the mean of the interval
    # if step function, then just use a nearest neighboor interpolator
    df_housing["maxDepth"] = (df_housing["hmin"] + df_housing["hmax"]) / 2
    # drop some columns
    df_housing = df_housing.drop(["hmin", "hmax"], axis=1)
    # convert maxDepth from cm to m
    df_housing["maxDepth"] /= 100
    # convert duration from h to s
    df_housing["duration"] *= 3600
    df_housing = df_housing.set_index(["maxDepth", "duration"])
    ds = df_housing.to_xarray()
    ds.attrs["units"] = {
        "dmg": "€2016/m2",
        "maxDepth": "m",
        "maxSpeed": "s",
    }
    ds.attrs["name"] = "h"
    return ds


def format_p(path) -> xr.Dataset:
    """
    Get formatted public damage functions from Floodam Excel file.
    """
    df_public = pd.read_excel(path, header=[0, 1], sheet_name=0)
    df_public.columns = pd.Index(
        [
            "hmin",
            "hmax",
            "duration",
            "education",  # établissements scolaires
            "firefighters",  # établissements d'incendies et de secours
            "townTechnicalServices",  # centres techniques municipaux
            "townhall",  # mairies/centres administratifs
            "police",  # commisariats de police / gendarmerie
            "housing",  # hébergements
            "health",  # établissements de santé
        ]
    )

    # format duration
    df_public["duration"] = [
        24 if duration == "<48h" else 72 for duration in df_public["duration"]
    ]
    # only keep max depth as the mean of the interval
    # if step function, then just use a nearest neighboor interpolator
    df_public["maxDepth"] = (df_public["hmin"] + df_public["hmax"]) / 2
    # drop some columns
    df_public = df_public.drop(["hmin", "hmax"], axis=1)
    # convert maxDepth from cm to m
    df_public["maxDepth"] /= 100
    # convert duration from h to s
    df_public["duration"] *= 3600
    df_public = df_public.set_index(["maxDepth", "duration"])
    ds = df_public.to_xarray()
    ds.attrs["units"] = {
        "dmg": "€2016/m2",
        "maxDepth": "m",
        "duration": "s",
    }
    ds.attrs["name"] = "p"
    return ds


def format_c(path) -> list:
    """
    Get formatted commercial damage functions from Floodam Excel file.
    """
    # batiment.surface
    batisurf = pd.read_excel(path, sheet_name="batiment.surface")
    # equipement.stock.employe
    stockemp = pd.read_excel(path, sheet_name="equipement.stock.employe")
    # total.employe
    totalemp = pd.read_excel(path, sheet_name="total.employe")

    def func(df_to_format: pd.DataFrame) -> xr.Dataset:
        # format d for nearest neighboor interpolation
        # > remove inf, np.interp takes care of extrapolation
        d_min = df_to_format["d.min"].replace(49, 48).replace(-np.inf, 0)
        d_max = df_to_format["d.max"].replace(np.inf, 96).replace(-np.inf, 96)
        # format h for nearest neighboor interpolation
        # > remove inf, np.interp takes care of extrapolation
        h_min = df_to_format["h.min"].replace(-np.inf, 0)
        # > since we take the mean later, add 1 to h.max
        h_max = (df_to_format["h.max"] + 1).replace(np.inf, 505)

        ds = (
            # generate new dataframe with modified columns,
            # adapted for nearest neighboor interpolation
            pd.concat(
                [
                    # copy the "alea" col, replacing marin by maritime
                    df_to_format["alea"].replace("marin", "maritime"),
                    # define "maxDepth" as the mean of d.min and d.max
                    # convert duration from h to s
                    (d_min + d_max).div(2).mul(3600).rename("duration"),
                    # define "maxDepth" as the mean of h.min and h.max
                    # convert maxDepth from cm to m
                    (h_min + h_max).div(2).div(100).rename("maxDepth"),
                    # finally, add all other columns
                    df_to_format[
                        df_to_format.columns.difference(
                            ["h.max", "h.min", "d.min", "d.max", "alea"]
                        )
                    ],
                ],
                axis=1,
            )
            # set maxDepth, duration and alea as multi index
            .set_index(["maxDepth", "duration", "alea"])
            # then convert to xarray dataset
            .to_xarray()
        )

        ds.attrs["units"] = {
            "maxDepth": "m",
            "duration": "s",
            "alea": "qualitative",
        }
        return ds

    batisurf = func(batisurf)
    stockemp = func(stockemp)
    totalemp = func(totalemp)

    batisurf.attrs["name"] = "batisurf"
    batisurf.attrs["units"]["dmg"] = "€2016/m2"
    stockemp.attrs["name"] = "stockemp"
    stockemp.attrs["units"]["dmg"] = "€2016/employee"
    totalemp.attrs["name"] = "totalemp"
    totalemp.attrs["units"]["dmg"] = "€2016/employee"

    # set index
    seuilemp = pd.read_excel(path, sheet_name="seuil.employe")
    seuilemp = seuilemp.set_index(["APE.05"])
    
    sirenemp = pd.read_excel(path, sheet_name="sirene.employe")
    # drop first line (only nan values) + set index
    sirenemp = sirenemp.drop(0).reset_index(drop=True).set_index("categorie")
    #
    # ds = xr.concat([batisurf, stockemp, totalemp], dim = 'type')\
    #     .assign_coords(type = ["batisurf", "stockemp", "totalemp"])
    #
    # ds.attrs['units']['type'] = 'qualitative'
    # ds.attrs['name'] = 'c'
    # return ds
    return batisurf, stockemp, totalemp, seuilemp, sirenemp


def format_ct(path) -> pd.DataFrame:
    """
    Get formatted correspondence table from Floodam Excel file.
    """
    df_ct = pd.read_excel(path, sheet_name="Typologie equipements publics")
    df_ct = df_ct[["NAF.05", "Fonctions de dommages"]]
    df_ct.columns = ["naf", "classe"]
    # create new functype column, to input directly in get_dmg
    df_ct["functype"] = [None] * len(df_ct)
    df_ct = df_ct.set_index("naf")

    for naf, _ in df_ct.iterrows():
        match df_ct.loc[naf, "classe"]:
            case "fonction de dommages hébergements":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "housing"
            case "fonction de dommages hébergements ":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "housing"
            case "fonction de dommages aux hébergements":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "housing"
            case "fonction de dommages mairies et centres administratifs":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "townhall"
            case "fonction de dommages police-gendarmerie":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "police"
            case "fonction de dommages établissements d’incendie et de secours":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "firefighters"
            case "fonction de dommages établissements scolaires":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "education"
            case "fonction de dommages établissements de santé":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "health"
            case "fonction de dommages établissements de santé ":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "health"
            case "fonction de dommages aux entreprises associée au code APE 64.19Z":
                df_ct.loc[naf, "functype"] = "c"
                df_ct.loc[naf, "classe"] = "6419Z"
            case "fonction de dommages aux entreprises associée au code APE 86.90B":
                df_ct.loc[naf, "functype"] = "c"
                df_ct.loc[naf, "classe"] = "8690B"
            case "fonction de dommages aux entreprises associée au code APE 73.20Z":
                df_ct.loc[naf, "functype"] = "c"
                df_ct.loc[naf, "classe"] = "7320Z"
            case "fonction de dommages centres techniques municipaux":
                df_ct.loc[naf, "functype"] = "p"
                df_ct.loc[naf, "classe"] = "townTechnicalServices"
            case "fonctions de dommages STEP (à venir)":
                df_ct.loc[naf, "functype"] = "WIP"
                df_ct.loc[naf, "classe"] = "WIP"
            case "fonctions de dommages STEU (à venir)":
                df_ct.loc[naf, "functype"] = "WIP"
                df_ct.loc[naf, "classe"] = "WIP"
            case "sans objet":
                pass
            case "diagnostic individuel ":
                pass
            case "sans objet (dommages associés aux logements)":
                pass
            case "fonction de dommages réseaux de transports":
                pass
            case "diagnostic individuel":
                pass
            case "mobile":
                pass
            case "fonctions de dommages traitement des déchets (à venir)":
                pass
            case _:
                raise ValueError(f">>> {df_ct.loc[naf, 'classe']}")

    df_ct = df_ct.dropna()
    return df_ct


def format_w(path) -> list:
    """
    Get formatted water treatment facilities damage functions from Floodam Excel file.
    """
    for sheet_name in ["Stations extensives", "Stations intensives "]:
        part1 = pd.read_excel(
            path, header=[0, 1, 2], sheet_name=sheet_name, nrows=52
        )
        part1.columns = part1.columns.to_flat_index()
        part2 = pd.read_excel(path, sheet_name=sheet_name, skiprows=55)
        if sheet_name == "Stations extensives":
            input_col = "maxSpeed"
        elif sheet_name == "Stations intensives ":
            input_col = "duration"
        else:
            raise ValueError()
        new_cols = [
            "hmin",
            "hmax",
            input_col,
            "alea",
            # take mean for nearest neighboor interpolation
            50,  # <100EH
            150,  # [100- 200 EH[
            350,  # [200- 500 EH[
            1250,  # [500- 2000 EH[
            6000,  # [2000- 10 000 EH[
            # for nearest interpolator to work, need to have 14 000
            14000,  # >= 10 000 EH
        ]
        part1.columns = new_cols
        part2.columns = new_cols
        df_w = pd.concat([part1, part2], axis=0)
        # format d for nearest neighboor interpolation
        # > since we take the mean later, add 1 to h.max
        df_w["hmax"] += 1
        # > remove inf, np.interp takes care of extrapolation
        df_w["hmin"] = df_w["hmin"].replace(-np.inf, 0)
        df_w["hmax"] = df_w["hmax"].replace(np.inf, 505)
        # > define maxDepth for nearest neighboor interpolation
        df_w["maxDepth"] = (df_w["hmin"] + df_w["hmax"]) / 2
        df_w["maxDepth"] /= 100  # cm to m
        # drop old d and h cols, drop alea since it is only fluvial
        df_w = df_w.drop(["hmin", "hmax", "alea"], axis=1)

        if sheet_name == "Stations extensives":
            df_w[input_col] = df_w[input_col].replace(
                {"faible à modérée": "low", "forte": "high"}
            )
        elif sheet_name == "Stations intensives ":
            # 24 and 72 for nearest neighboor interpolation
            df_w[input_col] = (
                df_w[input_col]
                .replace({"< 48h": 24, "> 48h": 72})
                .infer_objects()
            )
            df_w[input_col] *= 3600  # hours to seconds
        else:
            raise ValueError()
        # melting dataframe
        df_w = df_w.melt(id_vars=[input_col, "maxDepth"])
        df_w = df_w.rename(columns={"variable": "capacity"})
        ds = df_w.set_index(["maxDepth", input_col, "capacity"]).to_xarray()
        if sheet_name == "Stations extensives":
            extensive = ds["value"]
            extensive.attrs["units"] = {
                "dmg": "€2016/EH",
                "maxDepth": "m",
                "capacity": "EH",
                "maxSpeed": "qualitative",
            }
        elif sheet_name == "Stations intensives ":
            intensive = ds["value"]
            intensive.attrs["units"] = {
                "dmg": "€2016/EH",
                "maxDepth": "m",
                "capacity": "EH",
                "duration": "s",
            }
        else:
            raise ValueError()
    return extensive, intensive


def compute_sha256(filepath: str) -> str:
    """
    Return the SHA-256 hexdigest of a file on disk.
    """
    with open(filepath, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _dump_netcdf(obj: xr.Dataset | xr.DataArray, path: str) -> None:
    """
    Save an xarray object to netCDF, serializing dict attrs (units) to JSON.
    """
    obj = obj.copy(deep=False)
    for key, value in list(obj.attrs.items()):
        if not isinstance(value, (str, int, float, bool)):
            obj.attrs[key] = json.dumps(value)
    obj.to_netcdf(path)


def main() -> None:
    """
    Download any missing raw files, then precompile to netCDF/CSV + sha256 manifest.
    """
    for filename in SHA256CHECKSUMS:
        if not os.path.exists(os.path.join(DATA_DIR, filename)):
            print(f"{filename} not found, downloading raw floodam files")
            download_xls_files(datadir=DATA_DIR)
            break

    for filename, digest in SHA256CHECKSUMS.items():
        assert compute_sha256(os.path.join(DATA_DIR, filename)) == digest, (
            f"raw {filename} sha256 mismatch, refusing to precompile"
        )
    os.makedirs(OUT_DIR, exist_ok=True)

    def dump(obj, name: str) -> None:
        if isinstance(obj, (xr.Dataset, xr.DataArray)):
            path = os.path.join(OUT_DIR, f"{name}.nc")
            _dump_netcdf(obj, path)
        else:
            path = os.path.join(OUT_DIR, f"{name}.csv")
            obj.to_csv(path)
        print(f"wrote {path}")

    dump(format_a(os.path.join(DATA_DIR, "fa.xls")), "a")

    h = xr.concat(
        [
            format_h(os.path.join(DATA_DIR, "fh.xls")),
            format_h(os.path.join(DATA_DIR, "mh.xls")),
        ],
        dim="alea",
    ).assign_coords(alea=["fluvial", "maritime"])
    h.attrs["units"]["alea"] = "qualitative"
    dump(h, "h")

    p = xr.concat(
        [
            format_p(os.path.join(DATA_DIR, "fp.xls")),
            format_p(os.path.join(DATA_DIR, "mp.xls")),
        ],
        dim="alea",
    ).assign_coords(alea=["fluvial", "maritime"])
    p.attrs["units"]["alea"] = "qualitative"
    dump(p, "p")

    batisurf, stockemp, totalemp, seuilemp, sirenemp = format_c(
        os.path.join(DATA_DIR, "fc.xlsx")
    )
    dump(batisurf, "batisurf")
    dump(stockemp, "stockemp")
    dump(totalemp, "totalemp")
    dump(seuilemp, "seuilemp")
    dump(sirenemp, "sirenemp")

    dump(format_ct(os.path.join(DATA_DIR, "ct.xls")), "ct")

    wext, wint = format_w(os.path.join(DATA_DIR, "fw.xlsx"))
    dump(wext, "wext")
    dump(wint, "wint")

    with open(os.path.join(OUT_DIR, "sha256.txt"), "w") as f:
        for name in [
            "a",
            "h",
            "p",
            "batisurf",
            "stockemp",
            "totalemp",
            "seuilemp",
            "sirenemp",
            "ct",
            "wext",
            "wint",
        ]:
            filename = (
                f"{name}.nc"
                if os.path.exists(os.path.join(OUT_DIR, f"{name}.nc"))
                else f"{name}.csv"
            )
            f.write(
                f"{compute_sha256(os.path.join(OUT_DIR, filename))}  {filename}\n"
            )
    print("wrote sha256 manifest")


if __name__ == "__main__":
    main()
