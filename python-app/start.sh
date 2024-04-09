#!/bin/bash
export PIP_INDEX_URL=https://<add_repo_manager>/artifactory/api/pypi/pypi/simple && \
pip install --upgrade pip --trusted-host <repo_manager_host> && \
pip install --no-cache-dir -r requirements.txt --trusted-host artifactory.cnes.fr && \
echo 'install finish' && \
python3 grafana2prom.py