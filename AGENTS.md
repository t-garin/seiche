# AGENTS.md

## Isolated work directories

Each time an agent is spawned, it must work in its own isolated copy of the
repository, never directly in the master checkout:

- Create a git branch named `<uuid4>_<taskname>`. Get the uuid using python.
- Create a working directory named `<uuid4>_<taskname>`: a fresh clone of the
  repository with that branch checked out. Put it outside the master checkout,
  e.g. under `/tmp/opencode/<uuid4>_<taskname>`.
- Do all editing, testing and committing inside that working directory. This
  keeps concurrent agents from touching the master checkout or each other's
  files.
- Create a merge request into `master` only when the user explicitly asks. It might seem not possible to do a MR but try until you find the solution.

## Tools
- Use `uv` to run any python related commands.

## Container
- Always run seiche, its tests and its lint from inside the container, never
  directly on the host.
- Build the image with `just container-build`, then get a shell with
  `just container-run`.
- The image bundles the source, the dependencies, OpenTelemac and the data
  directories, so no host data needs to be mounted. Use only data already in
  the image: never mount host directories (e.g. with `-v`) when running the
  container, so results are reproducible and the run uses only image data. Run
  e.g. `podman run --rm seiche:latest -c "cd /seiche && just unittest"`.
- If `podman` is not installed, ask the user whether to set up podman first or
  run the commands directly on the host instead. Do not pick for them.

## Architecture

### Source files
- Sources files are located in `src/seiche`.
- `main_*.py` files hold the main logic.
- `format_*.py` files correctly format the multiple input data sources.
- `utils_*.py` files hold utility functions for some data types.
- Feel free to reorganize, create and/or delete source files as long as there are no subfolders in `src/seiche`.

## Code style
- Before writing any new code, always check whether a well-maintained third-party library already provides the needed functionality (e.g. numpy, scipy, shapely, xarray, rioxarray, pandas, scikit-image). Prefer calling the third-party function over hand-rolling an equivalent one, and reuse what the project already depends on.
- Follow PEP8.
- Always use type annotations.
- Always use docstrings. They should be numpy-style.
- Do not comment every line of code, only those with specific gotchas.
- Keep functions short.
- Use functional patterns when possible. 
- Use classes sparingly.

## Commit guidelines
- Keep diffs small and focused.
- Message format: [tag] title \n brief optional description.
- Tags can be 4-letters strings: 
    - "feat" for changes that add new features, config, or tooling that alters behaviour.
    - "move" for changes that move code around without changing the functionality.
    - "opti" for changes that optimize some part of the code for speed or memory usage.
    - "supr" for changes that remove dead code, old comments, or a function.
    - "docs" for changes that modify comments, docstrings, or /docs/*.md files.
    - "test" for test related changes.
    - "misc" for the rest.
- If they do not exist, add unittests for each part of the code that you modified. There should be 100% coverage. There should be at least a few unittests, and they should include edge cases. Feel free to reorganize, create and/or delete test files in the `/tests/` subfolder, as long as you do not touch `test_full_pipeline.py`. If you delete part of the code, delete the unittests accordingly.
- If the commit changed any line of actual code (not docstrings or comments) that is located in `src/seiche`, always run `just lint` and `just test` before commiting.
- Check that the documentation is up-to-date for the part of the code you modified.