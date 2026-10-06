# Flow

SEICHE is a pipeline, whose flow is described here. The methods are described [in the technical report](https://gitlab.com/garinto/technical-report-2023-2026/-/blob/main/main.pdf), and this current section is meant to discuss the implementation of such methods in the pipeline.

## Main loop

![files_call_graph](./files_call_graph.svg)

The pipeline is orchestrated as a functional chain of parts in `src/main.py`. Each part is a `(state: dict) -> dict` function: it receives the whole state, does its computation, and returns an updated state. The parts are declared in the `PIPELINE` registry and run in order by `run_pipeline`:

```py
PIPELINE: tuple[tuple[str, Callable[[dict], dict]], ...] = (
    ("dem", generate_or_load_dem),
    ("hazard", generate_hazard),
    ("impact_eco", impact_eco),
    ("impact_pop", impact_pop),
    ("plot", plot),
)
```

`run_pipeline` loops over the parts, skips the ones already marked as done in `state["done"]`, runs the others and dumps the whole state to `state.yml` in the output directory after each part. This makes the pipeline resumable: if a run crashes, the next one reloads `state.yml` and picks up where it left off.

The `state` dict carries everything between parts:

- `config`: the raw config file (derived values such as the polygon, EPSG or save names are computed on demand by `src/utils_state.py`),
- `config_path`: path to the input config file,
- `done`: parts already completed,
- `dem` / `hazard`: paths to the generated rasters, opened lazily when needed so memory is freed between parts.

Before the chain, `main()` sets up logging (`src/utils_qol.py`) and `initialize_state` (`src/utils_state.py`) builds the initial state from the config file: it loads the config, handles cold/hot runs (a cold run wipes the output dir) and loads the resume state. The parts are:

1 | `generate_or_load_dem` (`src/format_dem.py`): generate or load the DEM and store its path in the state. It is skipped when only user-provided hvt hazards are configured, since they don't need a DEM. Should be included directly in `src/main_hazards.py` at some point, since it is not relevant anywhere else.  

2 | `generate_hazard` (`src/main_hazards.py`): Generates 3-band hazard rasters stored in GeoTIFFs. The first band is H(x, y), the maximum water depth, V(x, y) the maximum water velocity and T(x, y) the flood duration, for the given event. This is the choosen convention, on which part 4 and 5 are based. The goal of this part of the code is to take the heterogenous data that can come from satelites, 2D hydrodynamic modelling, and transform them in these 3-band rasters. Alternatively, ready-made 3-band H/V/T rasters can be provided directly by the user (`path.inp.hvt`), in which case only reprojection/clipping is done. See [Hazard formatting](#hazard-formatting).

3 | `impact_eco` (`src/main_impact_eco.py`): Based on the 3-band rasters, this part of the code applies economic damage functions to land covers, in order to have a monetary estimation of the impact of a flood. See [Economic impact](#economic-impact).

4 | `impact_pop` (`src/main_impact_pop.py`): Based on the 3-band rasters, this part of the code is in charge of producing an estimation of the impact of a flood on the population. See [Social impact](#social-impact).

5 | `plot` (`src/main_plot.py`): After the computations are done, some automating reporting. See [Auto plotting](#auto-plotting).

## Pre-computation

## Hazard formatting

## Economic impact

## Social impact

## Auto plotting