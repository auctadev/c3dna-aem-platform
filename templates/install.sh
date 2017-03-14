#!/usr/bin/env bash

CONTROL_ALIAS="${1}"
API_V2_USER="${2}"
API_V2_PASSWORD="${3}"
INTERNAL_IP="${4}"
CONTROLLER_IP="${5}"
PLATFORM_ID="${6}"
CLUSTER_ID="${7}"
IMAGE="c3dna_platform"

appliance_config=configure_platform.sh

echo "$0 version 36 (build Thu Nov 19 16:45:24 CST 2015)"

#
# Create python sandbox
#
apt-get -y -qq update
apt-get -y -qq install python python-pip >/dev/null
pip install -q requests clc-sdk

#
# Validate functioning credentials
#
./preflight_checklist.sh "${API_V2_USER}" "${API_V2_PASSWORD}" &>> ~/clc_installer.log
error=$?
if [ $error -ne 0 ]; then
	exit $error
fi

# Manager files to start on boot
sed -i "/<INTERNALIP-KEY>.*/cinternalIP=${INTERNAL_IP}" $appliance_config
sed -i "/<CONTROLLERIP-KEY>.*/ccontrollerIP=${CONTROLLER_IP}" $appliance_config
sed -i "/<PLATFORMID-KEY>.*/cplatformID=${PLATFORM_ID}" $appliance_config
sed -i "/<CLUSTERID-KEY>.*/cclusterID=${CLUSTER_ID}" $appliance_config

#
# Changeing to Async
#
echo "Beginning install stage 2 (asynchronous)"
mkdir ~root/clc_installer
cp -R * ~root/clc_installer/
(cd ~root/clc_installer && setsid ./install_stage2.sh "${CONTROL_ALIAS}" "${API_V2_USER}" "${API_V2_PASSWORD}" "${IMAGE}") >>~/clc_installer.log 2>&1 &

