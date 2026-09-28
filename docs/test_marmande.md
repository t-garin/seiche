# Marmande

Marmande is a south-western French city, located on the Garonne river, a few dozens of kilometers upstream of Bordeaux. More precisely, the reach located between Tonneins ~> Marmande ~> La Réole has been the theater of many overlowing flooding events, especially in recent years, and was the object of many studies. For the latter, 2D-hydrodynamic models were created, ran, and analysed to understand the flooding events. It is a highly valuable water hazard source to use for an impact estimation, hence the choice of this test case. There, the flooded landcover is mostly agricultural, urban and industrial assets being a minority, nor is it a very dense area population-wise. But it is a perfect scenario to compare multiple water hazard representations, for example 2D-hydrodynamics vs remote sensing-based hazards.

Using the `download_seiche_data.py` script, 4 archives are available, corresponding to 4 flooding events that occured between 2019 and 2026, respectivelly named `marmande_2019` to `marmande_2026`. The following sections describe the inputs stored in each archives, whereas the last one shows excpected outputs, here only for the 2019 flood event.

Local copies were made in july 2024

## Inputs of marmande_2019

| file                    | src |
|-------------------------|-----|
| lf_2019_fr1.slf         | Local copy grabbed from: /archive/globc/thnguyen/fishstick/examples/python3/telapy_study/telemac2d/Garonne19TGRS/res_Garonne_2019_flood_FR1/Garonne_2019.slf
| hf_2019_k17.slf         | Local copy grabbed from: /scratch/globc/cassan/HYDRO/Garonne_Downstream_2023/2D-Data/Garonne_2019_flood/res_garonne2023_flood2019
| marmande_aoi.geojson    | Custom made by taking the intersection of the lf and hf extents.
| sirene_2019-12.csv      | Downloaded from: https://data.cquest.org/geo_sirene/v2019/2019/2019-12/StockEtablissementActif_utf8_geo.csv.gz
| rpg_2020.shp            | Downloaded from: https://data.cquest.org/registre_parcellaire_graphique/2020/RPG_2-0__SHP_LAMB93_R75_2020-01-01.7z
| bdtopo_bati_2019-12.shp | Downloaded from: https://data.cquest.org/ign/bdtopo/BDTOPO_3-0_2019-12-16/BDTOPO_3-0_TOUSTHEMES_SHP_LAMB93_D047_2019-12-16.7z.001
| rge_alti.tif            | Local copy grabbed from: /space/globc/cassan/SWIFT/GARONNE/data/merged_2023_v2_culvert_dike.tif
| /floodml/               | Local copy grabbed from: /archive/globc/FloodDAM/FloodML/FML
| esawc_2020.tif          | Downloaded from Copernicus DataSpace using OpenEO (https://openeo.dataspace.copernicus.eu/openeo/1.2)
| oso_2019.tif            | Downloaded from: https://geodes-portal.cnes.fr/
| demglo30_2011.tif       | Downloaded from Copernicus DataSpace using OpenEO (https://openeo.dataspace.copernicus.eu/openeo/1.2)
| filosofi_2019.gpkg      | Downloaded from: https://www.insee.fr/fr/statistiques/7655475?sommaire=7655515
| ghslpop_2020.tif        | Downloaded from: https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2020_GLOBE_R2023A_54009_100/V1-0/tiles/GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0_R4_C19.zip
Local copies were made in july 2024

## Inputs of marmande_2021

| file                    | src |
|-------------------------|-----|
| lf_2021_fr1.slf         | Local copy grabbed from: /archive/globc/thnguyen/fishstick/examples/python3/telapy_study/telemac2d/Garonne21TGRS/res_Garonne_2021_flood_FR1/Garonne_2021.slf
| lf_2021_run_true.slf    | Local copy grabbed from: /archive/globc/thnguyen/fishstick/examples/python3/telapy_study/telemac2d/Garonne21AGU/res_Garonne_2021_truth/Garonne_2021.slf
| hf_2021_k17.slf         | Local copy grabbed from: scratch/globc/cassan/HYDRO/Garonne_Downstream_2023/2D-Data/Garonne_2021_flood/res_garonne2023_flood2021_HF
| marmande_aoi.geojson    | See marmande_2019
| sirene_2021-02.csv      | Downloaded from: https://data.cquest.org/geo_sirene/v2019/2021/2021-02/StockEtablissementActif_utf8_geo.csv.gz
| rpg_2022.shp            | Downloaded from: https://data.cquest.org/ign/rpg/2022/RPG_2-0__SHP_LAMB93_R75_2022-01-01.7z
| bdtopo_2021-12.gpkg     | Downloaded from: https://data.cquest.org/ign/bdtopo/BDTOPO_3-0_2021-12-15/BDTOPO_3-0_TOUSTHEMES_GPKG_LAMB93_D047_2021-12-15.7z
| rge_alti.tif            | Local copy grabbed from: /space/globc/cassan/SWIFT/GARONNE/data/merged_2023_v2_culvert_dike.tif
| /floodml/               | Local copy grabbed from: /archive/globc/FloodDAM/FloodML/FML
| esawc_2021.tif          | Downloaded from Copernicus DataSpace using OpenEO (https://openeo.dataspace.copernicus.eu/openeo/1.2)
| oso_2021.tif            | Downloaded from: https://geodes-portal.cnes.fr/
| demglo30_2011.tif       | Downloaded from Copernicus DataSpace using OpenEO (https://openeo.dataspace.copernicus.eu/openeo/1.2)
| filosofi_2021.gpkg      | https://www.insee.fr/fr/statistiques/8735162?sommaire=8735243
| ghslpop_2020.tif        | Downloaded from: https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A/GHS_POP_E2020_GLOBE_R2023A_54009_100/V1-0/tiles/GHS_POP_E2020_GLOBE_R2023A_54009_100_V1_0_R4_C19.zip

## Inputs of marmande_2022

## Inputs of marmande_2026