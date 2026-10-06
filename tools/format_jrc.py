"""
Precompile the raw JRC Excel file into CSVs that dmgfunc_jrc reads at runtime.

Run with:
    uv --script format_jrc.py

Outputs are written to data/jrc/precompiled/ along with a sha256.txt manifest
used by dmgfunc_jrc to detect corrupted CSVs.
"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "numpy",
#     "openpyxl",
#     "pandas",
#     "xlrd",
# ]
# ///
import hashlib
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "jrc")
XLSX_PATH = os.path.join(
    DATA_DIR, "copy_of_global_flood_depth-damage_functions__30102017.xlsx"
)
OUT_DIR = os.path.join(DATA_DIR, "precompiled")

# expected sha256 of the raw xlsx, so we only precompile from a known-good file
XLSX_SHA256 = "5b944b59167e6cf5215885cccd99fae762c40a2e6c9f8d5b5d2afdad2cf5ddad"

SHEETS = {
    "dmgfac.csv": ("format_dmgfac", {}),
    "hmaxdmg.csv": (
        "format_hci_maxdmg",
        {"sheet_name": "MaxDamage-Residential"},
    ),
    "cmaxdmg.csv": (
        "format_hci_maxdmg",
        {"sheet_name": "MaxDamage-Commercial"},
    ),
    "imaxdmg.csv": (
        "format_hci_maxdmg",
        {"sheet_name": "MaxDamage-Industrial"},
    ),
    "tmaxdmg.csv": ("format_t_maxdmg", {}),
    "rmaxdmg.csv": ("format_r_maxdmg", {}),
    "amaxdmg.csv": ("format_a_maxdmg", {}),
}


def format_dmgfac(filepath: str) -> pd.DataFrame:
    """
    Get formatted damage factor from JRC Excel file.
    """
    df_dmgfac = pd.read_excel(
        filepath,
        sheet_name="Damage functions",
        header=[1, 2],
        index_col=0,
    )
    df_dmgfac.columns = df_dmgfac.columns.to_flat_index()
    df_dmgfac.index = df_dmgfac.index.rename("class")
    df_dmgfac.columns = pd.Index(
        [
            "depth",
            "dmgEU",
            "dmgNA",
            "dmgSA",
            "dmgAS",
            "dmgAF",
            "dmgOC",
            "dmgGL",
            "stdEU",
            "stdNA",
            "stdSA",
            "stdAS",
            "stdAF",
            "stdOC",
            "stdGL",
        ]
    )
    df_dmgfac = df_dmgfac.reset_index()
    df_dmgfac["class"] = df_dmgfac["class"].ffill()
    df_dmgfac = df_dmgfac.replace(
        {
            "Residential buildings": "h",
            "Commercial buildings": "c",
            "Industrial buildings": "i",
            "Transport": "t",
            "Infrastructure - roads": "r",
            "Agriculture": "a",
        },
    )
    df_dmgfac = df_dmgfac.set_index("class")
    df_dmgfac = df_dmgfac.replace("-", pd.NA)
    return df_dmgfac


def format_hci_maxdmg(filepath: str, sheet_name: str) -> pd.DataFrame:
    """
    Initialize the maximum damage dataframe for residential, commercial, or industrial buildings.
    """
    maxdmgdf = pd.read_excel(filepath, sheet_name=sheet_name, header=[0, 1, 2])
    maxdmgdf.columns = maxdmgdf.columns.to_flat_index()
    maxdmgdf.columns = pd.Index(
        [
            "country",
            "building-structure",
            "building-content",
            "building-total",
            "landuse-total",
            "object-total",
        ]
    )
    maxdmgdf = maxdmgdf.set_index("country")
    maxdmgdf["a3"] = _get_a3_from_names(filepath, maxdmgdf.index.tolist())
    maxdmgdf["continent"] = _get_continents_from_a3(maxdmgdf["a3"].tolist())
    return maxdmgdf


def format_a_maxdmg(
    filepath: str, sheet_name: str = "MaxDamage-Agriculture"
) -> pd.DataFrame:
    """
    Initialize the maximum damage dataframe for agriculture.
    """
    maxdmgdf = pd.read_excel(filepath, sheet_name=sheet_name, header=[0, 1])
    maxdmgdf.columns = maxdmgdf.columns.to_flat_index()
    maxdmgdf.columns = pd.Index(
        [
            "country",
            "maxdmg",
            "area",
        ]
    )
    maxdmgdf = maxdmgdf.set_index("country")
    maxdmgdf["a3"] = _get_a3_from_names(filepath, maxdmgdf.index.tolist())
    maxdmgdf["continent"] = _get_continents_from_a3(maxdmgdf["a3"].tolist())
    return maxdmgdf


def format_r_maxdmg(
    filepath: str, sheet_name: str = "MaxDamage-Infrastructure"
) -> pd.DataFrame:
    """
    Initialize the maximum damage dataframe for infrastructur and roads.
    """
    # hardcoded regional max damages (€/m2)
    regional_max = {"EU": 25, "AS": 4, "OC": 7}

    # hardcoded regional GDPs (2010 US$)
    regional_gdp = {"EU": 43097, "AS": 1913, "OC": 51800}  # europe, asia, oceania

    return _apply_regional_maxdmg(
        _get_local_gdp(filepath, sheet_name),
        regional_max,
        regional_gdp,
        default_max=70,
        default_gdp=36297,
        usa_max=245,
        usa_gdp=48377,
    )


def format_t_maxdmg(
    filepath: str, sheet_name: str = "MaxDamage-Transport"
) -> pd.DataFrame:
    """
    Initialize the maximum damage dataframe for transport.
    """
    # hardcoded regional max damages (€/m2)
    regional_max = {"EU": 751, "SA": 215, "AS": 209}

    # hardcoded regional GDPs (2010 US$)
    regional_gdp = {"EU": 43097, "SA": 10978, "AS": 2834}

    return _apply_regional_maxdmg(
        _get_local_gdp(filepath, sheet_name),
        regional_max,
        regional_gdp,
        default_max=392,
        default_gdp=18970,
    )


def _apply_regional_maxdmg(
    df_maxdmg: pd.DataFrame,
    regional_max: dict[str, float],
    regional_gdp: dict[str, float],
    default_max: float,
    default_gdp: float,
    usa_max: float | None = None,
    usa_gdp: float | None = None,
) -> pd.DataFrame:
    """
    Compute the max damage per row from the regional max damage and GDP.

    Continents not in the regional dicts fall back to the global values. If
    usa_max/usa_gdp are given, the USA row uses them instead of its continent.
    """
    for index, row in df_maxdmg.iterrows():
        local_gdp = row["local-gdp"]

        # Get continent GDP
        if usa_max is not None and usa_gdp is not None and row["a3"] == "USA":
            average_gdp = usa_gdp
            average_max = usa_max
        else:
            # default case, use global
            # works whether or not a3 code is available
            average_gdp = regional_gdp.get(row["continent"], default_gdp)
            average_max = regional_max.get(row["continent"], default_max)

        # if no local_gdp is provided, we use the default_gdp
        if np.isnan(local_gdp):
            local_gdp = default_gdp

        # formula given in excel file
        df_maxdmg.loc[index, "maxdmg"] = average_max * local_gdp / average_gdp

    return df_maxdmg


def _get_local_gdp(
    filepath: str, sheet_name: str = "MaxDamage-Infrastructure"
) -> pd.DataFrame:
    """
    Local gdp is identical between MaxDamage-Infrastructure and MaxDamage-Transport.
    """
    local_gdp = pd.read_excel(
        filepath,
        sheet_name=sheet_name,
        header=[1],
        skiprows=0,
        usecols=[0, 1],
    )
    local_gdp.columns = pd.Index(
        [
            "country",
            "local-gdp",
        ]
    )
    local_gdp = local_gdp.set_index("country")
    local_gdp["a3"] = _get_a3_from_names(filepath, local_gdp.index.tolist())
    local_gdp["continent"] = _get_continents_from_a3(local_gdp["a3"].tolist())
    return local_gdp


def _get_a3_from_names(filepath: str, countries_list: list[str]) -> list[str]:
    """
    Replace country names with their corresponding ISO 3166 a3 codes.

    e.g. Afghanistan -> AFG

    For this we use the MaxDamage-Data sheet.
    """
    df_a3 = pd.read_excel(
        filepath,
        sheet_name="MaxDamage-Data",
        header=[1],
        usecols=[0, 1],
    )
    df_a3.columns = df_a3.columns.to_flat_index()
    df_a3.columns = pd.Index(
        [
            "country",
            "a3_code",
        ]
    )
    df_a3 = df_a3.set_index("country")
    return df_a3.loc[countries_list, "a3_code"].to_numpy().tolist()


def _get_continents_from_a3(a3_list: list[str]) -> list[str]:
    """
    Return the continents given a list of a3 codes.

    got a csv from https://gist.github.com/stevewithington/20a69c0b6d2ff846ea5d35e5fc47f26c
    and put in jrc-data/countries.csv.

    - CHA, KOS, SCG, WBK were not in the orginial csv but present in jrc excel file
        Channel Islands, Kosovo, Serbia, West Bank and Gaza
        they were put respectively in NA, EU, EU, AS

    - Armenia, Azerbaidjan, Cyprus, Georgia,
        Kazakhstan, Russia, Turkey
        were in EU and AS, i choose to keep AS

    TODO: for these countries, do interp between EU and AS
    """
    df_countries = pd.read_csv(
        os.path.join(DATA_DIR, "countries.csv"),
        index_col="Three_Letter_Country_Code",
        # DONT PARSE NAN OTHERWISE
        # 'NA': north america is parsed as nan
        # na_filter=False
        na_values=[""],
        keep_default_na=False,
    )

    return [
        df_countries.loc[a3, "Continent_Code"]
        # detect NaN by checking the type being float or not
        # doesnt seem robust but is a 1 time thing so should be ok
        if type(a3) is not float
        else np.nan
        for a3 in a3_list
    ]


def compute_sha256(filepath: str) -> str:
    """
    Return the SHA-256 hexdigest of a file on disk.
    """
    with open(filepath, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main() -> None:
    """
    Precompile every JRC sheet to CSV and write a sha256 manifest.
    """
    assert compute_sha256(XLSX_PATH) == XLSX_SHA256, (
        "raw xlsx sha256 does not match, refusing to precompile"
    )
    os.makedirs(OUT_DIR, exist_ok=True)

    manifest = {}
    for filename, (func_name, kwargs) in SHEETS.items():
        df = globals()[func_name](XLSX_PATH, **kwargs)
        outpath = os.path.join(OUT_DIR, filename)
        df.to_csv(outpath)
        manifest[filename] = compute_sha256(outpath)
        print(f"wrote {outpath}")

    with open(os.path.join(OUT_DIR, "sha256.txt"), "w") as f:
        for filename, digest in manifest.items():
            f.write(f"{digest}  {filename}\n")
    print(f"wrote sha256 manifest for {len(manifest)} files")


if __name__ == "__main__":
    main()
