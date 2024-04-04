#!/bin/bash
export PIP_INDEX_URL=https://galpinth:/artifactory/api/pypi/pypi/simple && \
pip install --upgrade pip --trusted-host artifactory.cnes.fr && \
pip install --no-cache-dir -r requirements.txt --trusted-host artifactory.cnes.fr && \
echo 'install finish' && \
python3 grafana2prom.py