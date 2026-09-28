# Chinon

## Telemac2D runs

As part of [Q. BONASSIES's PhD thesis](https://theses.fr/2026UTLSP031), Telemac2D SWE simulations were launched on this Chinon extent. Moreover, a lot of work has been done in terms of [data assimilation](https://en.wikipedia.org/wiki/Data_assimilation), using the [Ensemble Kalmann Filter Method](https://en.wikipedia.org/wiki/Ensemble_Kalman_filter), and multiple data sources. All these simulations can be used as input for the flood damage estimation, allowing to test their relevance in terms of flood risk assessment. 

Simulations taken from (in June 2026): 
- `/archive/globc/bonassies/Chinon/2D-Data/chinon_2024`
- `/archive/globc/bonassies/Chinon/2D-Data/chinon_cv`

### Assimilation Modes

The following assimilation modes were applied to the simulations:

- **Free Run**: A regular Telemac2D simulation with no data assimilation applied.
- **IDA (In-Situ Data Assimilation)**: Assimilation using in-situ measurement data.
- **RSDA (Remote Sensing Data Assimilation)**: Assimilation using satellite imagery.
- **FDA (Full Data Assimilation)**: Combined assimilation using both in-situ and remote sensing data.

### Data Sources

The used _in-situ_ data comes from the French VigiCrue stations network, and Sentinel-1 satellite images for remote sensing, unless "swot" is mentioned, in which case it was the SWOT satellite. SWOT provides data at given nodes of a hydrographic network, allowing it to assimilate it either as _in-situ_ or using the derived flood extents as remote sensing.

### Assimilation Metrics

The following suffixes indicate the assimilation metric applied:

- **_WSR**: Wet Surface Ratio derived from satellite imagery.
- **_CV**: Chan-Vese segmentation method. *(Note: This method requires further development.)*

For additional technical details, refer to Q. Bonassies's PhD thesis.

### EnKF Configuration

The **nodh** suffix indicates that the Ensemble Kalman Filter (EnKF) assimilation process:

- Adjusted only the friction coefficients and upstream flow
- Did **not** manually add or remove water during assimilation (unlike standard practice)

### Assimilated vs Validation variables

| **Run Name** | **Assimilation Mode** | **Data Source** | **Assimilation Metric** | **EnKF Configuration** |
|---|---|---|---|---|
| Free Run | No assimilation | N/A | N/A | N/A |
| IDA | In-Situ Data Assimilation | VigiCrue stations | Standard | Standard |
| IDA_CV | In-Situ Data Assimilation | VigiCrue stations | Chan-Vese segmentation | Standard |
| IDAswot | In-Situ Data Assimilation | SWOT satellite (as in-situ) | Standard | Standard |
| IDAswot_CV | In-Situ Data Assimilation | SWOT satellite (as in-situ) | Chan-Vese segmentation | Standard |
| RSDA_WSR | Remote Sensing Data Assimilation | Sentinel-1 satellite | Wet Surface Ratio | Standard |
| RSDA_CV | Remote Sensing Data Assimilation | Sentinel-1 satellite | Chan-Vese segmentation | Standard |
| RSDAswot_WSR | Remote Sensing Data Assimilation | SWOT satellite (as remote sensing) | Wet Surface Ratio | Standard |
| RSDAswot_CV | Remote Sensing Data Assimilation | SWOT satellite (as remote sensing) | Chan-Vese segmentation | Standard |
| FDA_WSR | Full Data Assimilation | VigiCrue + Sentinel-1 | Wet Surface Ratio | Standard |
| FDA_CV | Full Data Assimilation | VigiCrue + Sentinel-1 | Chan-Vese segmentation | Standard |
| FDAnodh_WSR | Full Data Assimilation | VigiCrue + Sentinel-1 | Wet Surface Ratio | No manual water adjustment (friction & flow only) |
| FDAnodh_CV | Full Data Assimilation | VigiCrue + Sentinel-1 | Chan-Vese segmentation | No manual water adjustment (friction & flow only) |
