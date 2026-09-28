"""
Helper script to generate MkDocs "Configuration" page,
based on the documentation provided in seiche_config_builder.py
"""

import re
import seiche_config_builder
from markdownify import markdownify

# keep all the cells named doc_*
doc_cells = [name for name in dir(seiche_config_builder) if name.startswith("doc_")]
print(f"Generating MkDocs docs/config.md from {doc_cells} marimo cells.")

# add custom message at the beginning
all_docs = []
all_docs.append("""
# Configuration

To build your configuration file, it is recommended to use the SEICHE Config Builder.
It can be accessed through the `just config` command. 
This page is extracted from the documentation made available in the Config Builder,
and is meant to be a quick look-up reference.
""")

# for each cell, run it, and get the Md representation of the output
for cell_name in doc_cells:
    cell = getattr(seiche_config_builder, cell_name)
    output, _ = cell.run()
    all_docs.append(markdownify(output._repr_html_()))

# save to docs/config.md
with open("./docs/config.md", "w") as f:
    f.write("\n\n".join(all_docs))