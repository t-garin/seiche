# display useful information
help:
    just --list

# run ruff check and format on src
lint:
    uv run ty check src
    uv run ruff check src
    uv run ruff format src

# run the test suite
test:
    uv sync --group test
    uv run pytest --cov=src/seiche --cov-report=term-missing tests/

# run all tests except the full pipeline
unittest:
    uv sync --group test
    uv run pytest --cov=src/seiche --cov-report=term-missing tests/ --ignore=tests/test_full_pipeline.py

# build and open the documentation
docs:
    fuser -k 1312/tcp || true
    uv sync --group docs
    uv run pyan3 -m src/seiche/ --module-level --svg > docs/files_call_graph.svg
    uv run tools/_seiche_config_builder_to_mkdocs.py
    uv run mkdocs serve -o -a localhost:1312

# open the configuration builder
config:
    @uvx marimo run --sandbox tools/seiche_config_builder.py

# compile the presentation to HTML
[private]
pres:
    marp --theme-set docs/pres --output docs/pres/2026-09-29-v0.1.0-presentation.html docs/pres/2026-09-29-v0.1.0-presentation.md
    uv run python docs/pres/_embed_images.py docs/pres/2026-09-29-v0.1.0-presentation.html
    
# run seiche
run *ARGS:
    uv run src/seiche/main.py {{ARGS}}

# run the whole pipeline under scalene (CPU, memory, GPU), HTML + terminal
run-with-profile *ARGS:
    uv run scalene run --gpu src/seiche/main.py {{ARGS}}
    uv run scalene view --cli --reduced
    uv run scalene view --reduced --standalone

# download seiche data
download *ARGS:
    uv run --script tools/download_seiche_data.py {{ARGS}}

# preprocess Sentinel-2 snow (SNW) and cloud (CLD) cover
filter-s2 *ARGS:
    uv run --script tools/filter_s2.py {{ARGS}}

# remove snow from Sentinel-1 tiles with the magenta filter
filter-s1 *ARGS:
    uv run --script tools/filter_s1.py {{ARGS}}

# precompile the raw Floodam Excel files
format-floodam:
    uv run --script tools/format_floodam.py

# precompile the raw JRC Excel file
format-jrc:
    uv run --script tools/format_jrc.py

# preprocess in-situ Hydroportail observations
hydroportail:
    uv run --script tools/preprocess_in_situ_hydroportail.py

# download ESA WorldCover and Copernicus DEM30 from Copernicus Data Space
download-esawc-demcop30:
    uv run --script tools/_download_esawc_demcop30_from_copdataspace.py

# download OSO rasters from Geodes (needs pygeodes-config.json in cwd)
download-oso:
    uv run --script tools/_download_oso_from_geodes.py

[private]
edit-config:
    @uvx marimo edit --sandbox tools/seiche_config_builder.py
