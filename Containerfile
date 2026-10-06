FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

RUN apt-get -y update \
 && apt-get install -y git curl build-essential libgeos-dev libproj-dev libgdal-dev \
    libgl1 libglib2.0-0 libsm6 libxrender1 libgomp1 \
 && curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /seiche/bin \
 && rm -rf /var/lib/apt/lists/*

COPY . /seiche

WORKDIR /seiche
RUN export PATH="/seiche/bin:$PATH" \
 && just download --opentelemac --unzip /seiche/opentelemac \
 && rm /seiche/opentelemac/opentelemac_python3_20240430.zip \
 && uv sync --all-groups --locked

ENV PATH="/seiche/.venv/bin:/seiche/bin:$PATH" \
    SEICHE_OPENTELEMAC_PATH=/seiche/opentelemac/opentelemac_python3_20240430

ENTRYPOINT ["/bin/bash"]
