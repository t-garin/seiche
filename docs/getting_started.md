## Getting the code

As of now, the repository is not opensource, it is meant to be, but in the mean time you will need to have access to the private repo. If you do you can either clone using `https`:

```sh
git clone https://gitlab.com/cerfacs/globc/seiche.git
```

and you will be asked to put your id and gitlab password everytime you want to pull the code; or you can setup a `SSH` key and clone using `SSH`:

```sh
git clone git@gitlab.com:cerfacs/globc/seiche.git
```

In order to setup your `SSH` key, please refer to https://docs.gitlab.com/user/ssh/. Here is a TL;DR: 

### (optional) Setting up SSH keys

1. Go in your `.ssh` folder.
    ```sh
    cd $HOME/.ssh
    ```
2. Check if you already have a `id_ed25519`	and `id_ed25519.pub` file using `ls`:
    ```sh
    >>> ls -l
    ... id_ed25519
    ... id_ed25519.pub
    ```
3. If you don't, use the following to generate the files.
    ```sh
    ssh-keygen -t ed25519
    ```
4. DO NOT SHARE `id_ed25519`, it is your private key and should remain private.
5. Your public key (that can be public) `id_ed25519.pub` should look something like this:
    ```
    ssh-ed25519 XXX...XXX user@machine
    ```
    Go into your GitLab profile, under **Access > SSH keys > Add new key** and copy-paste `id_ed25519.pub` in the appropriate field. Set up expiration date, title ..etc. and you should be good to go !

## Installation

There are two ways to get seiche up and running. The recommended one is to use
the provided OCI container, which bundles the source, the dependencies, a local
copy of the OpenTelemac python APIs and the test data. If you prefer not to use
a container, you can install everything on your host with `./install_seiche.sh`.

### (recommended) Using the container

An OCI container image is provided that bundles the source, the dependencies, a
local copy of the OpenTelemac python APIs and the test data. It is a convenient
way to run seiche and its tests in a reproducible environment without installing
anything on your host. It requires [podman](https://podman.io/) (with its
machine started, e.g. `podman machine start`).

Build the image (produces an OCI image tagged `seiche:latest`):

```sh
just container-build
```

Then get an interactive shell inside it:

```sh
just container-run
```

Or run a single command without entering the shell:

```sh
podman run --rm seiche:latest -c "cd /seiche && just test"
```

The image already contains all the data it needs, so use only the data bundled
inside it: never mount host directories (e.g. with `-v`) when running the
container. This keeps runs reproducible and makes sure only image data is used.

### (alternative) Installing on your host

A convenient `./install_seiche.sh` script allows to install everything you need
to run the code, mainly `uv` as package manager, `just` as a command runner and
a local copy of the OpenTelemac python APIs, that will be sourced correctly.
Simply run:

```sh
>>> ./install_seiche.sh
```
For more details or manual installation tips, see [this section of the contributing guide](contributing.md#manual-installation).

## Getting data

Then, to get test data, the script `tools/download_seiche_data.py` can be used, either directly or using `just download`.

```sh
>>> just download
uv run tools/download_seiche_data.py 
usage: download_seiche_data.py [-h] [--opentelemac] [--marmande] [--marmande_2019] [--marmande_2021]
                               [--marmande_2022] [--marmande_2026] [--stomer] [--ohio] [--chinon] [--all]
                               [--unzip]
                               [dest]

Download and unzip archives from a remote server.

positional arguments:
  dest             Destination folder (default: current working directory)

options:
  -h, --help       show this help message and exit
  --opentelemac    Download opentelemac archive
  --marmande       Download marmande archive
  --marmande_2019  Download marmande_2019 archive
  --marmande_2021  Download marmande_2021 archive
  --marmande_2022  Download marmande_2022 archive
  --marmande_2026  Download marmande_2026 archive
  --stomer         Download stomer archive
  --ohio           Download ohio archive
  --chinon         Download chinon archive
  --all            Download all available archives
  --unzip          Unzip downloaded archives
```

If `dest` (the positional argument) is left empty, then it will download and unzip in the current directory.

It is a convenient way of downloading specific zip archives from [mercure.cerfacs.fr/seiche](https://mercure.cerfacs.fr/seiche/), the urls are already stored within the script so no need to supply them. So for example if you want to download the `opentelemac` API, the `stomer`, `marmande_2019` and `marmande_2021` test cases ([see here for more details](test_stomer.md)) and unzip everything directly in your `../../Downloads` folder, you can use it like so:

```sh
>>> just download --marmande_2019 --marmande_2021 --opentelemac --stomer --unzip ../../Downloads/
dwnld opentelemac_python3_20240430.zip... 100.00%|██████████████████████████████████████████████████| 758k/758k [00:00<00:00, 2.09MB/s]
dwnld marmande_2019_inp.zip.............. 100.00%|██████████████████████████████████████████████████| 6.88G/6.88G [01:17<00:00, 88.5MB/s]   
dwnld marmande_2021_inp.zip.............. 100.00%|██████████████████████████████████████████████████| 9.42G/9.42G [01:46<00:00, 88.5MB/s]
dwnld stomer_inp.zip..................... 100.00%|██████████████████████████████████████████████████| 9.57G/9.57G [01:47<00:00, 89.0MB/s]
unzip opentelemac_python3_20240430.zip... 100.00%|██████████████████████████████████████████████████| 239/239 [00:00<00:00, 255.92it/s]
unzip marmande_2019_inp.zip.............. 100.00%|██████████████████████████████████████████████████| 40/40 [03:57<00:00,  5.93s/it]
unzip marmande_2021_inp.zip.............. 100.00%|██████████████████████████████████████████████████| 35/35 [05:13<00:00,  8.95s/it]
unzip stomer_inp.zip..................... 100.00%|██████████████████████████████████████████████████| 22022/22022 [19:00<00:00, 19.30it/s]
```

## Running the code

Once you have everything, `cd` into the root folder, and you should be able to run the code (given a [valid seiche_config.yml file](config.md)) like so:

```sh
just run seiche_config.yml
```

`uv` should detect the `pyproject.toml` file -- _if the current working directory is the root directory of the repo_ -- and the dependencies should be installed, given that you have an internet connection.

### Overriding config values

Individual config values can be overridden without editing the config file, by
repeating the `--override` (or `-o`) flag with `key: value` pairs. Values are
parsed as YAML, so `param.EPSG: 2154` stays an integer and
`param.cold_run: false` a boolean:

```sh
just run seiche_config.yml \
    --override="path.inp: /data/inp" \
    -o "path.out: /tmp/out" \
    -o "param.cold_run: false"
```

Keys must be existing config keys, and the last occurrence wins when a key is
repeated.

### (optional) Run `pytest` to check code integrity

The code should be fully tested after each commit thanks to GitLab's CI/CD pipelines. However, it can be a good practice to test the code before using it, to ensure no bugs slipped in somehow. For this purpose, you can run the following command:

```sh
just test
```

Among the tests, light, full-pipeline test cases are run, in the folders `tests/marmande_light` and `tests/stomer_light`, [see their description here](tests.md).


## (optional) Run headless/on HPC 

For some computations and on HPC, it is recommended to launch it using a job manager like SLURM. in the `slurms` directory, you can find an example of how to run SEICHE with SLURM. They all wrap the `just run` command, that allows to launch the computation, with additionnal cluster-specific infomations.

> ⚠️ They contain hardcoded informations like the log destination and more. You should adapt the `*.slurm` according to your specific HPC needs.

For example if you want to launch a computation on a cluster named `scylla`, you would use:

```sh
>>> cd seiche # be sure you are in the repo folder
>>> sbatch slurms/scylla.slurm tests/stomer_light/stomer_light.yml
```
Feel free to adapt them to your machine, or use a different job manager than SLURM!

