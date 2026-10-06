# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pyyaml>=6.0.3",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(
    app_title="SEICHE Config Builder",
    css_file="seiche_config_builder.css",
)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # SEICHE Config Builder

    The following notebook (made with `marimo`) is meant to be an all-in-one application helping you to create a well formated SEICHE config YAML file. Indeed, SEICHE is a pipeline where the user should never interact with the code itself, instead config files are expected as input of this app, to tell it how it should behave. `src/config_template.yml` is used to verify the input config file is well formated.

    To use this configuration builder properly, enter the desired value in the fields below, and press ENTER so that the notebook can properly register the value. At the bottom of the notebook there is a "Final configuration" section where you can see the file being generated. Finally, you can save the file either by copy-pasting the raw text in the "Final configuration" section, or provide a path and hit "Save" in the "Saving the config file" section.
    """)
    return


@app.cell
def _():
    import csv
    import os

    import marimo as mo
    import yaml

    # "if mo.app_meta().mode in ["run", "edit"]"
    # allows to keep the interactive behaviour while in notebook mode
    # but to disable some stuff when the documentation is being scrapped for mkdocs
    print(f"Current marimo mode: {mo.app_meta().mode}")
    return csv, mo, os, yaml


@app.cell(hide_code=True)
def doc_1_general(mo):
    param_expname = mo.ui.text(label = "`param.expname`")
    path_inp = mo.ui.text(label = "`path.inp`")
    path_out = mo.ui.text(label = "`path.out`")
    path_inp_poly = mo.ui.text(label = "`path.inp.POLY`")
    param_epsg = mo.ui.number(label = "`param.EPSG`", value = 3857)
    param_cold_run = mo.ui.switch(label = "`param.cold_run`", value = False)
    param_autoplot = mo.ui.switch(label = "`param.autoplot`", value = True)
    param_autoreport = mo.ui.switch(label = "`param.autoreport`", value = True)

    contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        contents.append(mo.md("## 1. Setting up paths and general parameters"))
    contents.append(mo.md(r"""
    The first step is setting up the paths of input and output files:

    >###**`param.expname`**
    `*(optional, str)* Name of the experiment, only useful for the result files names. If not provided, will be infered from the name of the provided config file. E.g.:`
    ```yaml
    param.expname: marmande_2019
    ```

    > ###**`path.inp`**
    `*(mandatory, str)* Path to the root folder holding the input files. E.g.:`
    ```yaml
    path.inp: /archive/garin/marmande_2019_inp
    ```

    > ###**`path.out`**
    `*(mandatory, str)* Path to the root folder holding the output files. E.g.:`
    ```yaml
    path.out: /archive/garin/marmande_2019_out
    ```
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        contents.append(mo.vstack([param_expname, path_inp, path_out]))

    contents.append(mo.md(r"""
    Then, you need to prodive a POLY and EPSG:

    >###**`path.inp.POLY`**
    `*(mandatory, vector database that can be opened with geopandas.read_file)* Relative path pointing to the work polygon, to which every data will be cliped to. E.g.:`
    ```yaml
    path.inp.POLY: marmande.geojson
    path.inp.POLY: subfolder/marmande.geojson
    ```

    >### **`param.EPSG`**
    `*(optional, int)* The [EPSG code](https://en.wikipedia.org/wiki/EPSG_Geodetic_Parameter_Dataset) to reproject the temporary and final data to. If not provided, will be extracted from POLY's file. E.g.:`
    ```yaml
    param.EPSG: 3857
    ```
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        contents.append(mo.vstack([path_inp_poly, param_epsg]))

    contents.append(mo.md(r"""
    And finally, some general parameters:

    >### **`param.cold_run`**
    `*(mandatory, bool)* Wheter or not to do a cold SEICHE run. If true, all previously compiled output files will be removed before executing the code. E.g.:`
    ```yaml
    path.cold_run: false
    ```

    >###**`param.autoplot`**
    `*(mandatory, boolean)* Wheter or not to plot automatical some of the temporary and output data. See main_plot.py and utils_plot.py. E.g.:`
    ```yaml
    path.autoplot: true
    ```

    >###**`param.autoreport`**
    `*(mandatory, boolean)* Wheter or not to automatically generate a PDF report of the run (configuration + plots) with Typst at the end of the pipeline. Uses the `typst` python package. See main_report.py. E.g.:`
    ```yaml
    path.autoreport: true
    ```
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        contents.append(mo.vstack([param_cold_run, param_autoplot, param_autoreport]))

    #
    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"1. Setting up paths and general parameters":mo.vstack(contents)})
    else:
        _output = mo.vstack(contents)
    _output
    return (
        param_autoplot,
        param_autoreport,
        param_cold_run,
        param_epsg,
        param_expname,
        path_inp,
        path_inp_poly,
        path_out,
    )


@app.cell(hide_code=True)
def doc_2_dem(mo):
    path_inp_dem_root = mo.ui.text(label = "`path.inp.dem.root`")
    path_inp_dem_filter_key = mo.ui.text(label = "`path.inp.dem.filter_key`")
    path_inp_dem_epsg = mo.ui.number(label = "`path.inp.dem.EPSG`")

    dem_contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        dem_contents.append(mo.md("## 2. DEM input"))

    dem_contents.append(mo.md(r"""
    A Digital Elevation Model (or DEM) is a mandatory piece of data that is needed for SEICHE to generate the water hazards. It is used to estimate the water depth derived from Binary Flood Masks, and also to compute the water depth from the free surface available in the Telemac2D .slf files.

    >###**`path.inp.dem.root`**
    `*(optional, str)* Relative subfolder holding all the DEM tiles, all files in this folder and subfolders will be considered. If they are in the root folder, leave it to a single dot. E.g.:`
    ```yaml
    path.inp.dem.root: dem # will look in path.inp/dem
    path.inp.dem.root: . # will look in path.inp directly
    ```

    >###**`path.inp.dem.filter_key`**
    `*(optional, str)* Only files with this key in the file name will be kept. Use something like ".tif" to keep all GeoTIFF files the recursive search finds. E.g.:`
    ```yaml
    path.inp.dem.filter_key: .tif # keeps every .tif it finds in the folder
    path.inp.dem.filter_key: demcop30 # keeps every file that has "demcop30" in it
    ```

    >###**`path.inp.dem.EPSG`**
    `*(optional, int)* For some DEMs in old .asc format, EPSG needs to be provided manually here. E.g.:`
    ```yaml
    path.inp.dem.EPSG: 2154 # only taken into account if .asc dem tiles
    path.inp.dem.EPSG: null # no need if dem tiles are .tif
    ```
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        dem_contents.append(mo.vstack([path_inp_dem_root, path_inp_dem_filter_key, path_inp_dem_epsg]))


    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"2. DEM input":mo.vstack(dem_contents)})
    else:
        _output = mo.vstack(dem_contents)
    _output
    return path_inp_dem_epsg, path_inp_dem_filter_key, path_inp_dem_root


@app.cell(hide_code=True)
def doc_3_a_bfm(mo):
    bfm_contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        bfm_contents.append(mo.md("## 3-A. Binary Flood Masks (optional)"))

    bfm_contents.append(mo.md(r""" 
    ## 3-A-i. BFM paths

    >###**`path.inp.bfm.root`**
    `*(optional, str)* Root folder holding all the Binary Flood Masks, all files in this folder and subfolders will be considered.`

    >###**`path.inp.bfm.filter_key`**
    `*(optional, str)* Only files with this key in the file name will be kept. Use something like ".tif" to keep all GeoTIFF files the recursive search finds. For example in FloodML, use "POST" to only use these products.`

    >###**`path.inp.bfm.files2ignore`**
    `*(optional, str)* Files to ignore from computation stored in a text file, with one path per line. TODO: It's probably better to just include it inside the config directly rather than having a separate text file?`

    >###**`path.inp.bfm.regex`**
    `*(optional, str)* REGEX used to infer the datetime from filename. For example, "(\\\\d{8})T(\\\\d{6})" points to YYYYMMDDTHHMMSS (one more backslash compared to python's re). Could be improved to be more general.`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        path_inp_bfm_root = mo.ui.text(label = "`path.inp.bfm.root`")
        path_inp_bfm_regex = mo.ui.text(label = "`path.inp.bfm.regex`", value = r"(\\d{8})T(\\d{6})")
        path_inp_bfm_filter_key = mo.ui.text(label = "`path.inp.bfm.filter_key`")
        path_inp_bfm_files2ignore = mo.ui.text(label = "`path.inp.bfm.files2ignore`")
        bfm_contents.append(mo.vstack([path_inp_bfm_root, path_inp_bfm_regex, path_inp_bfm_filter_key, path_inp_bfm_files2ignore]))

    bfm_contents.append(mo.md(r"""        
    ## 3-A-ii. BFM parameters

    >###**`param.bfm.flooded_threshold`**
    `*(mandatory, in seconds)* Once duration is computed, apply this threshold in order to get the overall Binary Flood Mask (BFM) of the event.`

    >###**`param.bfm.target_resolution`**
    `*(mandatory, in meters)* duration will be computed at this target resolution, before being reprojected to match the DEM. For example, if DEM is at 1m, and BFMs are natively at 10m, put target_resolution = 10: duration will be computed at 10m and reprojected to 1m later, only when needed. Also, if the DEM is at 30m, and the BFMs at 10m, we can put the target resolution at 30, since in all cases, the information will be lost when reprojecting on the DEM. In meters as long as the EPSG is projected (not geodesic), otherwise in degrees.`

    >###**`param.bfm.start_date`**
    `*(mandatory, date)* Well-formated date string like "YYYY-MM-DD" indicating the begining of the experiment, used to filter input data.`

    >###**`param.bfm.end_date`**
    `*(mandatory, date)* Well-formated date string like "YYYY-MM-DD" indicating the end of the experiment, used to filter input data.`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        param_bfm_flooded_threshold = mo.ui.number(label = "`param.bfm.flooded_threshold`", value = 0)
        param_bfm_target_resolution = mo.ui.number(label = "`param.bfm.target_resolution`", value = 10)
        param_bfm_start_date = mo.ui.date(label = "`param.bfm.start_date`")
        param_bfm_end_date = mo.ui.date(label = "`param.bfm.end_date`")
        bfm_contents.append(mo.vstack([param_bfm_flooded_threshold, param_bfm_target_resolution, param_bfm_start_date, param_bfm_end_date]))

    bfm_contents.append(mo.md(r""" 
    ## 3-A-iii. DEFENDED

    >###**`use.defended.fwdet_c`**
    `*(mandatory, bool)* Wheter or not to use FwDET method, with cubic interpolation, for depth estimation.`

    >###**`use.defended.fwdet_l`**
    `*(mandatory, bool)* Wheter or not to use FwDET method, with linear interpolation, for depth estimation.`

    >###**`use.defended.fwdet_n`**
    `*(mandatory, bool)* Wheter or not to use FwDET method, with nearest neighboor interpolation, for depth estimation.`

    >###**`use.defended.hand_a`**
    `*(mandatory, bool)* Wheter or not to use HAND method for slope correction, before doing a depth estimation. -a indicates it will be applied on the whole extent at once.`

    >###**`use.defended.hand_e`**
    `*(mandatory, bool)* Wheter or not to use HAND method for slope correction, before doing a depth estimation. -e indicates it will be applied on each connected water groups.`

    >###**`param.defended.hand_threshold`**
    `*(optional, float)* For HAND, an accumulation threshold is needed. [See pysheds doc](https://mattbartos.com/pysheds/hand.html).`

    >###**`use.defended.simple_a`**
    `*(mandatory, bool)* Here, no slope correction is performed before doing a depth estimation. -a indicates it will be applied on the whole extent at once.`

    >###**`use.defended.simple_e`**
    `*(mandatory, bool)* Here, no slope correction is performed before doing a depth estimation. -e indicates it will be applied on each connected water groups.`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        use_defended_fwdet_c = mo.ui.switch(label="`use.defended.fwdet_c`")
        use_defended_fwdet_l = mo.ui.switch(label="`use.defended.fwdet_l`")
        use_defended_fwdet_n = mo.ui.switch(label="`use.defended.fwdet_n`")
        use_defended_hand_a = mo.ui.switch(label="`use.defended.hand_a`")
        use_defended_hand_e = mo.ui.switch(label="`use.defended.hand_e`")
        param_defended_hand_threshold = mo.ui.number(label="`param.defended.hand_threshold`")
        use_defended_simple_a = mo.ui.switch(label="`use.defended.simple_a`")
        use_defended_simple_e = mo.ui.switch(label="`use.defended.simple_e`")
        bfm_contents.append(mo.vstack(
            [
                use_defended_fwdet_c,
                use_defended_fwdet_l,
                use_defended_fwdet_n,
                use_defended_hand_a,
                use_defended_hand_e,
                param_defended_hand_threshold,
                use_defended_simple_a,
                use_defended_simple_e,
            ]
        ))

    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"3-A. Binary Flood Masks (optional)":mo.vstack(bfm_contents)})
    else:
        _output = mo.vstack(bfm_contents)
    _output
    return (
        param_bfm_end_date,
        param_bfm_flooded_threshold,
        param_bfm_start_date,
        param_bfm_target_resolution,
        param_defended_hand_threshold,
        path_inp_bfm_files2ignore,
        path_inp_bfm_filter_key,
        path_inp_bfm_regex,
        path_inp_bfm_root,
        use_defended_fwdet_c,
        use_defended_fwdet_l,
        use_defended_fwdet_n,
        use_defended_hand_a,
        use_defended_hand_e,
        use_defended_simple_a,
        use_defended_simple_e,
    )


@app.cell(hide_code=True)
def _(mo):
    MAX_SLF_FILES = 20
    n_slf_files = mo.ui.slider(0, MAX_SLF_FILES, label="Number of `.slf` files:")
    param_slf_pixel_size = mo.ui.number(label = "`param.slf.pixel_size`", value = 10)

    slf_files = [
        [
            mo.ui.text(label = f"`nickname`"),
            mo.ui.text(label = f"`filepath`"),
            mo.ui.number(label = f"`espg`"),
            mo.ui.text(value = "VITESSE U", label = f"`xspeedVarname`"),
            mo.ui.text(value = "VITESSE V", label = f"`yspeedVarname`"),
            mo.ui.text(value = "HAUTEUR D'EAU", label = f"`depthVarname`"),
            mo.ui.number(value = 0.05, label = f"`depthThreshold`", start = 0, step = 0.01),
            mo.ui.text(value = "SURFACE LIBRE", label = f"`freesurfVarname`"),
        ]
        for i in range(MAX_SLF_FILES)
    ]
    return n_slf_files, param_slf_pixel_size, slf_files


@app.cell(hide_code=True)
def doc_3_b_slf(mo, n_slf_files, param_slf_pixel_size, slf_files):
    slf_contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        slf_contents.append(mo.md("## 3-B. Telemac2D .slf files (optional)"))

    slf_contents.append(mo.md("""
    >###**`param.slf.pixel_size`**
    `*(optional, int)* Target pixel size (in meters) used to rasterize the Telemac2D outputs. This single value applies to all the .slf files listed in path.inp.slf. E.g.:`
    ```yaml
    param.slf.pixel_size: 10
    ```

    >###**`path.inp.slf`**
    `*(optional, list[dict])* List of dictionaries containing informations about used .slf files. E.g.:`
    ```yaml
    path.inp.slf:
      - nickname:        slf_hf_2021_k17
          filepath:        Garonne2023_flood2021_K17.slf
          epsg:            2154
          xspeedVarname:   VITESSE U
          yspeedVarname:   VITESSE V
          depthVarname:    HAUTEUR D'EAU
          freesurfVarname: SURFACE LIBRE
          depthThreshold:  0.05
      - nickname:        slf_lf_2021_fr1
          filepath:        Garonne_2021_FR1.slf
          epsg:            27563
          xspeedVarname:   VITESSE U
          yspeedVarname:   VITESSE V
          depthVarname:    HAUTEUR D'EAU
          freesurfVarname: SURFACE LIBRE
          depthThreshold:  0.05
    ```

    >####**`nickname`**
    `*(mandatory, str)* Identifier string used when saving output files.`

    >####**`filepath`**
    `*(mandatory, str)* Path pointing to the file.`

    >####**`epsg`**
    `*(mandatory, int)* [EPSG](https://en.wikipedia.org/wiki/EPSG_Geodetic_Parameter_Dataset) of the Selafin file coordinates.`

    >####**`xspeedVarname`**
    `*(mandatory, str)* Variable pointing to the speed on the x-axis of the file.`

    >####**`yspeedVarname`**
    `*(mandatory, str)* Variable pointing to the speed on the y-axis of the file.`

    >####**`freesurfVarname`**
    `*(mandatory, str)* Variable pointing to the water depth of the file.`

    >####**`depthVarname`**
    `*(mandatory, str)* Variable pointing to the water depth of the file.`

    >####**`depthThreshold`**
    `*(mandatory, float)* Value above which the simulated water will be considered. Usefull to set at like 5cm to remove some simulation abberations (check the unit using slf.varunits). If you fully trust your simulation, set it at 0.`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        slf_contents.append(n_slf_files)
        if n_slf_files.value > 0: 
            slf_contents.append(param_slf_pixel_size)
        slf_contents.append(
            mo.ui.tabs({
                f"{i+1}":mo.vstack(slf_file)
                for (i, slf_file) in enumerate(slf_files)
                if i < n_slf_files.value
            })
        )



    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"3-B. Telemac2D's .slf files (optional)":mo.vstack(slf_contents)})
    else:
        _output = mo.vstack(slf_contents)
    _output
    return


@app.cell(hide_code=True)
def _(mo):
    MAX_HVT_FILES = 20
    n_hvt_files = mo.ui.slider(0, MAX_HVT_FILES, label="Number of user-provided hvt rasters:")
    hvt_files = [
        [
            mo.ui.text(label = f"`nickname`"),
            mo.ui.text(label = f"`filepath`"),
        ]
        for i in range(MAX_HVT_FILES)
    ]
    return n_hvt_files, hvt_files


@app.cell(hide_code=True)
def doc_3_c_hvt(mo, n_hvt_files, hvt_files):
    hvt_contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        hvt_contents.append(mo.md("## 3-C. User-provided H/V/T hazard rasters (optional)"))

    hvt_contents.append(mo.md(r"""
    >###**`path.inp.hvt`**
    `*(optional, list[dict])* List of dictionaries pointing to ready-made 3-band hazard rasters. The bands must be, in order: H (max water depth), V (max water velocity) and T (flood duration). SEICHE skips the slf/bfm hazard generation and only reprojects/clips these rasters to the study area. E.g.:`
    ```yaml
    path.inp.hvt:
      - nickname:        my_hazard
          filepath:        my_hazard_hvt.tif
    ```

    >####**`nickname`**
    `*(mandatory, str)* Identifier string used when saving output files.`

    >####**`filepath`**
    `*(mandatory, str)* Path pointing to the 3-band raster (H, V, T).`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        hvt_contents.append(n_hvt_files)
        hvt_contents.append(
            mo.ui.tabs({
                f"{i+1}":mo.vstack(hvt_file)
                for (i, hvt_file) in enumerate(hvt_files)
                if i < n_hvt_files.value
            })
        )

    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"3-C. User-provided H/V/T hazard rasters (optional)":mo.vstack(hvt_contents)})
    else:
        _output = mo.vstack(hvt_contents)
    _output
    return


@app.cell(hide_code=True)
def _(mo):
    n_files_esawc = mo.ui.slider(0, 20, label = "Number of landcover files for ESAWC:")
    n_files_oso23 = mo.ui.slider(0, 20, label = "Number of landcover files for OSO23:")
    n_files_bdtopo = mo.ui.slider(0, 20, label = "Number of landcover files for BDTOPO:")
    n_files_rpg = mo.ui.slider(0, 20, label = "Number of landcover files for RPG:")
    n_files_sirene = mo.ui.slider(0, 20, label = "Number of landcover files for SIRENE:")
    return (
        n_files_bdtopo,
        n_files_esawc,
        n_files_oso23,
        n_files_rpg,
        n_files_sirene,
    )


@app.cell(hide_code=True)
def doc_4_lcv(
    mo,
    n_files_bdtopo,
    n_files_esawc,
    n_files_oso23,
    n_files_rpg,
    n_files_sirene,
):
    filepath = mo.ui.text()
    esawc_files = mo.ui.array([filepath]*n_files_esawc.value)
    oso23_files = mo.ui.array([filepath]*n_files_oso23.value)
    bdtopo_files = mo.ui.array([filepath]*n_files_bdtopo.value)
    rpg_files = mo.ui.array([filepath]*n_files_rpg.value)
    sirene_files = mo.ui.array([filepath]*n_files_sirene.value)

    lcv_contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        lcv_contents.append(mo.md("## 4. Landcover"))

    lcv_contents.append(mo.md(r"""
    >###**`path.inp.lcv.*`**
    `*(optional, list[str])* List of path pointing to the files of a given landcover dataset. If multiple files are listed, they will be merged before doing the damage estimation. Keep the list formating even if only one file. For example:`
    ```yaml
    path.inp.lcv.esawc:
        - lcvsubfolder/esawc_tile1.tif
        - lcvsubfolder/esawc_tile2.tif

    path.inp.lcv.oso23:
        - OSO_RASTER_20230101.tif
    ```
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        lcv_contents.append(mo.ui.tabs({
            "ESAWC": mo.vstack([n_files_esawc, esawc_files]),
            "OSO23": mo.vstack([n_files_oso23, oso23_files]),
            "BDTOPO": mo.vstack([n_files_bdtopo, bdtopo_files]),
            "RPG": mo.vstack([n_files_rpg, rpg_files]),
            "SIRENE": mo.vstack([n_files_sirene, sirene_files]),
        }))

    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"4. Land cover":mo.vstack(lcv_contents)})
    else:
        _output = mo.vstack(lcv_contents)
    _output
    return (
        bdtopo_files,
        esawc_files,
        filepath,
        oso23_files,
        rpg_files,
        sirene_files,
    )


@app.cell(hide_code=True)
def _(mo):
    MAX_N_CONDITIONS = 20
    n_files_ghslpop = mo.ui.slider(0, 20, label = "Number of files for GHSLOPOP:")
    n_files_filosofi = mo.ui.slider(0, 20, label = "Number of files for FILOSOFI:")
    n_conditions = mo.ui.slider(0, MAX_N_CONDITIONS, label="Number of population conditions:")
    return MAX_N_CONDITIONS, n_conditions, n_files_filosofi, n_files_ghslpop


@app.cell(hide_code=True)
def doc_5_pop(
    MAX_N_CONDITIONS,
    filepath,
    mo,
    n_conditions,
    n_files_filosofi,
    n_files_ghslpop,
):
    ghslpop_files = mo.ui.array([filepath]*n_files_ghslpop.value)
    filosofi_files = mo.ui.array([filepath]*n_files_filosofi.value)

    condition_names = [
        mo.ui.text(label = f"`name`", value = "always_true")
        for i in range(MAX_N_CONDITIONS)
    ]
    condition_exprs = [
        mo.ui.text(label = f"`expr`", value = "True")
        for i in range(MAX_N_CONDITIONS)
    ]

    pop_contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        pop_contents.append(mo.md("## 5. Population datasets"))

    pop_contents.append(mo.md(r"""
    >###**`path.inp.pop.filosofi`**
    `*(optional, list[str])* List of path pointing to the shapefiles of INSEE's Filosofi. Keep the list formating even if only one file. E.g.:`
    ```yaml
    path.inp.pop.filosofi:
        - filosofi_2019_met.gpkg
        - filosofi_2019_mart_.gpkg
        - filosofi_2019_reun_.gpkg
    ```

    >###**`path.inp.pop.ghslpop`**
    `*(optional, list[str])* List of path pointing to the GeoTIFFs of JRC's GHSL-Pop. Keep the list formating even if only one file. E.g.:`
    ```yaml
    path.inp.pop.ghslpop:
        - ghslpop_2025_tile1.tif
        - ghslpop_2025_tile2.tif
    ```

    >###**`param.pop.conditions`**
    `*(mandatory, dict[str, str])* Map a condition name to a boolean expression on the hazard variables h (water depth), v (water velocity) and t (flood duration). Expressions are evaluated in a restricted namespace (no builtins); only h, v, t, True and False are reachable, plus whatever public methods h/v/t expose (e.g. pandas/xarray methods such as .quantile()). Each condition masks the population layer to the pixels/rows where it holds; the masked result is saved per condition name. Use "True" to keep all population. E.g.:`
    ```yaml
    param.pop.conditions:
        all_people: "True"
        is_above_30cm: "h > 0.3"
        is_touched_by_water: "h > 0"
        deep_or_fast: "(h > 0.5) | (v > 0.2)"
        extreme_quartile: "(h > h.quantile(0.75)) & (v > v.quantile(0.75)) & (t > t.quantile(0.75))"
    ```
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        condition_tabs = mo.ui.tabs({
            f"{i+1}": mo.vstack([condition_names[i], condition_exprs[i]])
            for i in range(MAX_N_CONDITIONS)
            if i < n_conditions.value
        })
        pop_contents.append(mo.ui.tabs({
            "ghslpop": mo.vstack([n_files_ghslpop, ghslpop_files]),
            "filosofi": mo.vstack([n_files_filosofi, filosofi_files]),
            "conditions": mo.vstack([n_conditions, condition_tabs]),
        }))

    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"5. Population datasets":mo.vstack(pop_contents)})
    else:
        _output = mo.vstack(pop_contents)
    _output
    return condition_exprs, condition_names, filosofi_files, ghslpop_files


@app.cell(hide_code=True)
def doc_6_dmgfuncs(csv, mo, os):
    dmg_contents = []
    if mo.app_meta().mode not in ["run", "edit"]:
        dmg_contents.append(mo.md("## 6. Damage functions"))

    dmg_contents.append(mo.md(r"""
    >###**`use.dmg.floodam`**
    `*(mandatory, bool)* Wheter or not to use Floodam as a damage function.`

    >###**`use.dmg.jrc`**
    `*(mandatory, bool)* Wheter or not to use JRC's damage functions.`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        use_dmg_jrc = mo.ui.switch(label = "`use.dmg.jrc`")
        use_dmg_floodam = mo.ui.switch(label = "`use.dmg.floodam`")
        dmg_contents.append(mo.vstack([use_dmg_jrc, use_dmg_floodam]))

    dmg_contents.append(mo.md(r"""
    >###**`param.floodam.alea`**
    `*(optional, in ["fluvial", "maritime"])* Either a river (overflowing) hazard, or a maritime submersion. Will only be used if use.dmg.floodam: True, will crash if not provided in this case.`

    >###**`param.floodam.season`**
    `*(optional, in ["automne", "hiver", "printemps", "été"])* When computing agricultural damages, floodam needs to know the season. Will only be used if use.dmg.floodam: True, will crash if not provided in this case.`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        param_floodam_alea = mo.ui.dropdown(
            options=["fluvial", "maritime"],
            label="`param.floodam.alea`",
            searchable=True,
        )
        param_floodam_season = mo.ui.dropdown(
            options=["automne", "hiver", "printemps", "été"],
            label="`param.floodam.season`",
            searchable=True,
        )
        dmg_contents.append(mo.vstack([param_floodam_alea, param_floodam_season]))

    dmg_contents.append(mo.md(r"""
    >###**`param.jrc.a3`**
    `*(mandatory)* ISO 3166-1 alpha-3 country code, to dispatch which JRC damage function to use. *E.g.: France -> FRA.*`

    >###**`param.jrc.region`**
    `*(mandatory, in ["eu", "na", "sa", "as", "af", "oc", "gl"])* 2 letters continent code, to dispatch which JRC damage function to use. Central America is included in "SA". When unspecified, the "GL" (Global) region can be used also. This should not be necessary, see format_jrc._get_continents_from_a3, should be changed in the future.`
    """))

    if mo.app_meta().mode in ["run", "edit"]:
        countries_csv = os.path.join(
            os.path.dirname(__file__), "..", "data", "jrc", "countries.csv"
        )
        with open(countries_csv) as _f:
            param_jrc_a3 = mo.ui.dropdown(
                options=sorted(
                    {
                        row["Three_Letter_Country_Code"]
                        for row in csv.DictReader(_f)
                        if row["Three_Letter_Country_Code"]
                    }
                ),
                label="`param.jrc.a3`",
                searchable=True,
            )
        param_jrc_region = mo.ui.dropdown(
            options=["eu", "na", "sa", "as", "af", "oc", "gl"],
            label="`param.jrc.region`",
            searchable=True,
        )
        dmg_contents.append(mo.vstack([param_jrc_a3, param_jrc_region]))

    if mo.app_meta().mode in ["run", "edit"]:
        _output = mo.accordion({"6. Damage functions":mo.vstack(dmg_contents)})
    else:
        _output = mo.vstack(dmg_contents)
    _output
    return (
        param_floodam_alea,
        param_floodam_season,
        param_jrc_a3,
        param_jrc_region,
        use_dmg_floodam,
        use_dmg_jrc,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Final configuration
    """)
    return


@app.cell
def _(
    bdtopo_files,
    condition_exprs,
    condition_names,
    esawc_files,
    filosofi_files,
    ghslpop_files,
    mo,
    n_conditions,
    n_slf_files,
    oso23_files,
    param_autoplot,
    param_autoreport,
    param_bfm_end_date,
    param_bfm_flooded_threshold,
    param_bfm_start_date,
    param_bfm_target_resolution,
    param_cold_run,
    param_defended_hand_threshold,
    param_epsg,
    param_expname,
    param_floodam_alea,
    param_floodam_season,
    param_jrc_a3,
    param_jrc_region,
    param_slf_pixel_size,
    path_inp,
    path_inp_bfm_files2ignore,
    path_inp_bfm_filter_key,
    path_inp_bfm_regex,
    path_inp_bfm_root,
    path_inp_dem_epsg,
    path_inp_dem_filter_key,
    path_inp_dem_root,
    path_inp_poly,
    path_out,
    rpg_files,
    sirene_files,
    slf_files,
    hvt_files,
    n_hvt_files,
    use_defended_fwdet_c,
    use_defended_fwdet_l,
    use_defended_fwdet_n,
    use_defended_hand_a,
    use_defended_hand_e,
    use_defended_simple_a,
    use_defended_simple_e,
    use_dmg_floodam,
    use_dmg_jrc,
    yaml,
):
    config = {}

    # 1. Setting up paths and general parameters
    config["param.expname"] = param_expname.value or None
    config["path.inp"] = path_inp.value or None
    config["path.out"] = path_out.value or None
    #
    config["path.inp.POLY"] = path_inp_poly.value or None
    config["param.EPSG"] = param_epsg.value or None
    #
    config["param.cold_run"] = param_cold_run.value
    config["param.autoplot"] = param_autoplot.value
    config["param.autoreport"] = param_autoreport.value

    # 2. DEM input
    config["path.inp.dem.root"] = path_inp_dem_root.value or None
    config["path.inp.dem.filter_key"] = path_inp_dem_filter_key.value or None
    config["path.inp.dem.EPSG"] = path_inp_dem_epsg.value or None

    # 3-A. BFM
    # i, paths
    config["path.inp.bfm.root"] = path_inp_bfm_root.value or None
    config["path.inp.bfm.regex"] = path_inp_bfm_regex.value or None
    config["path.inp.bfm.filter_key"] = path_inp_bfm_filter_key.value or None
    config["path.inp.bfm.files2ignore"] = path_inp_bfm_files2ignore.value or None
    # ii, params
    config["param.bfm.flooded_threshold"] = param_bfm_flooded_threshold.value or None
    config["param.bfm.target_resolution"] = param_bfm_target_resolution.value or None
    config["param.bfm.start_date"] = param_bfm_start_date.value or None
    config["param.bfm.end_date"] = param_bfm_end_date.value or None
    # iii, defended
    config["use.defended.fwdet_c"] = use_defended_fwdet_c.value
    config["use.defended.fwdet_l"] = use_defended_fwdet_l.value
    config["use.defended.fwdet_n"] = use_defended_fwdet_n.value
    config["use.defended.hand_a"] = use_defended_hand_a.value
    config["use.defended.hand_e"] = use_defended_hand_e.value
    config["param.defended.hand_threshold"] = param_defended_hand_threshold.value or None
    config["use.defended.simple_a"] = use_defended_simple_a.value
    config["use.defended.simple_e"] = use_defended_simple_e.value

    # 3-B. SLF
    config["param.slf.pixel_size"] = param_slf_pixel_size.value or None
    config["path.inp.slf"] = [
        {
            "nickname":slf_file[0].value,
            "filepath":slf_file[1].value,
            "epsg":slf_file[2].value,
            "xspeedVarname":slf_file[3].value,
            "yspeedVarname":slf_file[4].value,
            "depthVarname":slf_file[5].value,
            "freesurfVarname":slf_file[6].value,
            "depthThreshold":slf_file[7].value,
        }
        for i, slf_file in enumerate(slf_files)
        if i < n_slf_files.value
    ] or None

    # 3-C. HVT
    config["path.inp.hvt"] = [
        {
            "nickname": hvt_file[0].value,
            "filepath": hvt_file[1].value,
        }
        for i, hvt_file in enumerate(hvt_files)
        if i < n_hvt_files.value
    ] or None

    # 4. Landcover
    config["path.inp.lcv.esawc"] = [filepath.value for filepath in esawc_files] or None
    config["path.inp.lcv.oso23"] = [filepath.value for filepath in oso23_files] or None
    config["path.inp.lcv.bdtopo"] = [filepath.value for filepath in bdtopo_files] or None
    config["path.inp.lcv.rpg"] = [filepath.value for filepath in rpg_files] or None
    config["path.inp.lcv.sirene"] = [filepath.value for filepath in sirene_files] or None

    # 5. Population
    config["path.inp.pop.ghslpop"] = [filepath.value for filepath in ghslpop_files] or None
    config["path.inp.pop.filosofi"] = [filepath.value for filepath in filosofi_files] or None
    config["param.pop.conditions"] = {
        condition_names[i].value: condition_exprs[i].value
        for i in range(n_conditions.value)
    } or None

    # 6. Damage functions
    config["use.dmg.jrc"] = use_dmg_jrc.value
    config["use.dmg.floodam"] = use_dmg_floodam.value
    config["param.floodam.alea"] = param_floodam_alea.value
    config["param.floodam.season"] = param_floodam_season.value
    config["param.jrc.a3"] = param_jrc_a3.value
    config["param.jrc.region"] = param_jrc_region.value

    yaml_config = yaml.dump(config)
    with mo.redirect_stdout():
        print(yaml_config)
    return (yaml_config,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Saving the config file
    """)
    return


@app.cell
def _(mo):
    path_to_config = mo.ui.text(placeholder = "/path/to/seiche_config.yml", full_width=True)
    save_config_trigger = mo.ui.run_button(label="Save")

    mo.vstack([path_to_config, save_config_trigger])
    return path_to_config, save_config_trigger


@app.cell
def _(path_to_config, save_config_trigger, yaml_config):
    if save_config_trigger.value:
        with open(path_to_config.value, "w") as f:
            f.write(yaml_config)
    return


if __name__ == "__main__":
    app.run()
