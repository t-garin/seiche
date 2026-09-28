# Contributing

In /dev are some stuff that could be implemented but are not in production.

## Dev Tooling

### Commands

The project uses [just](https://just.systems/man/en/) to manage its build and test commands. They are described in the `justfile`, and if you have `just` installed you can see the list by running `just` on its own or `just help`.

### Package manager

This project uses [uv](https://docs.astral.sh/uv/) to manage the dependencies and the packages.

### Manual installation

If you do not want or cannot use the `./install_seiche.sh` script, here are the following steps:

#### `uv`

Make sure you have [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed, for example using: 

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### `just`

Make sure you have [`just`](https://just.systems/man/en/) installed, for example using (from: [https://just.systems/man/en/pre-built-binaries.html](https://just.systems/man/en/pre-built-binaries.html)): 

```sh
# create ~/bin
mkdir -p ~/bin

# download and extract just to ~/bin/just
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/bin

# add `~/bin` to the paths that your shell searches for executables
# this line should be added to your shell's initialization file,
# e.g. `~/.bashrc` or `~/.zshrc`
export PATH="$PATH:$HOME/bin"

# just should now be executable
just --help
```

It allows to read the `justfile` and load useful commands like `lint`, `test`, `docs`, and `run` that you can call using `just test` for example. For more details on `just`, just type `just` in the command line and help will be displayed.  

If you do not want to or cannot install just, you can also invoke it using `uv` like so:

```sh
uvx --from rust-just just --help
```

#### (optional) Setting up OpenTelemac Python API

If you plan on using `.slf` files with `seiche`, then you need to install some scripts to read Telemac2D files. They are not available on PyPi, Conda and so forth, so you will need to manually install them. You can either [build from source](https://gitlab.pam-retd.fr/otm/telemac-mascaret/-/blob/main/BUILDING.md), or use the folder made available by `download_seiche_data.py`. In both cases, you will need to set the `SEICHE_OPENTELEMAC_PATH` environment variable, so that the python script knows where to find it. 

⚠️ If you only export the environment variable once, it will be gone when you log out of your session. To make it permanent, add the following line to your `.bashrc`: 

```sh
export SEICHE_OPENTELEMAC_PATH="/path/to/opentelemac_python3_20240430"
```

### GitLab CI/CD

> MAYBE gitlab CD/CI should directly point to just commands ??? to explore how to use it

GitLab's _Continuous Integration and Continuous Delivery (or Deployment)_ (CI/CD) allows to automate some part of the development process. It is setup in the `.gitlab-ci.yml` file, at the root of the repo. Here -- and for now -- 3 actions are automated:

1. **Linting**: using `ruff`, the code quality is verified at each commit. The rules are described under `[tool.ruff]` and `[tool.ruff.lint]` in the `pyproject.toml` file. (_With GitLab free, the Code Quality Widget is not visible, but could be under Analytics > Code Quality if hosted on GitLab Premium. In the mean time, check the CI/CD pipeline logs, or run `ruff` locally_)

2. **Testing**: `pytest` is run with coverage at every commit to ensure nothing got broken in the process. If the pipeline failed, check the logs to identify which test failed due to the new commit. A coverage badge is available on the `README.md` to quickly assess how much of the code is actually tested, check the CI/CD logs for a more exhaustive breakdown.

3. **Documentation:** `mkdocs` is used to generate documentation at each commit in the `master` branch -- for example the full API reference using `mkdocs-api-autonav`. The rest of the docs can be found in the `/docs/` folder and `mkdocs.yml` file.

## Guidelines

### Commits

Since I worked mostly alone on the project, my commits are sometimes a bit goofy (+ I tend to do a lot of them for very little changes). Before copying the code over, more than 1000 of them were done on my personnal GitHub repo, with the same energy. All this to say that I don't have specific guidelines as of now for commiting, but it should be discussed in the future.

### AI

See AGENTS.md

## Todo

See TODO.md

### Known issues

- the sha256 signatures computed are not the same depending on the system on which the code is ran, probably some metadata issue. I have no idea how to fix this for now (maybe docker ?).

### Ideas

So much stuff. Here are some ideas:

- Review logging to make it clearer -> on top of .log files, each main_* function generates a report.json and everything gets compiled in a nicely formated Typst .pdf or .html -> [see here](https://typst.app/blog/2025/automated-generation/). This behaviour could be controled in a parameter in the config like `seiche.reporting: ["txt", "pdf", "html"] | null`. Some extra stuff could be logged like sha256 signatures of input, tmp and output files, to make sure an experiment is reproductible, and could be controlled with a config parameter like `seiche.check_sha256: true | false`. Or maybe just do this during testing ? 

- If faster data processing times are needed, switching to more modern frameworks, like using `zarr` instead of  `xarray` and `netCDF`, `polars` or a full database like `PostGreSQL` instead of `geopandas`, building parallelism from the start, or even rewriting parts of the code in other languages like `Julia` or `Rust` are all very tempting and should be done if required. However, if this tool is only used for occasional analyses, on small enough spatial extents, it could well be unreasonable optimization. Seems fun though!!