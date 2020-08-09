#!/bin/bash
set -ueo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_DIR=$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)
TMP_DIR=$(mktemp -d)

FUNCTIONS_DIR="${SCRIPT_DIR}/functions"
OUT_DIR="${REPO_DIR}/deploy"

pushd "${TMP_DIR}"

# main code and requirements
cp -r "${REPO_DIR}/wx_explore" .
cp -r "${REPO_DIR}/requirements.txt" "requirements.txt"

# azure specific config stuff
cp "${SCRIPT_DIR}/host.json" .
cp "${SCRIPT_DIR}/local.settings.json" .

for func in ${FUNCTIONS_DIR}/*; do
    if [ ! -d "${func}" ]; then continue; fi

    fn=$(basename "$func")

    echo "Building ${fn}"

    cp -r "${func}" "${fn}"

    find . -name .mypy_cache -exec rm -rf {} +
    find . -name \*.pyc -delete

    docker run -it -v "$(pwd):/host" mcr.microsoft.com/azure-functions/python:3.0.14120-python3.6-buildenv /bin/bash -c 'cd /host; pip3 install --target /host/.python_packages/lib/site-packages -r requirements.txt'

    func azure functionapp publish vtxwx-worker --no-build

    #mv tmp.*.zip "${OUT_DIR}/azure-$(basename $func)-$(date '+%Y-%m-%d-%H-%M-%S').zip"

    #rm -rf "${fn}"
done

popd

rm -rf "${TMP_DIR}"
