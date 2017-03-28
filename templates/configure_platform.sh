#!/bin/bash
##
# @name: configure_platform.sh
# @version: 1.1
# @date: 02/02/2017
# @author: Gregory Callea gcallea@auctacognitio.net
#
##

#Parameters
#===========
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FILE_NAME=`basename "$0"`

#Input
internalIP="{{ansible_ssh_host}}"
publicIP="{{publicIP}}"
controllerIP="{{controllerIP}}"
platformID="{{platformID}}"
clusterID="{{clusterID | d('CTL_Cloud') }}"

#Vps
VPS_LN=ctl.bp.aem.c3dna.net
vpsURL="http://$VPS_LN/adobe-aem"
vpsConfFile="platformIndex.txt"

#Download Index File
wget $vpsURL/$vpsConfFile -P .

#User
OWNER=cccuser
CCCUSER_PASSWORD=cccDNA2013!
USER_HOME=/home/$OWNER

#Software
CCC_HOME=$USER_HOME/ccc
BLUEPRINT_DIR=$USER_HOME/blueprint_c3dna_ext/
echo $CCCUSER_PASSWORD | sudo -Sp "" -u $OWNER mkdir -p $BLUEPRINT_DIR

LOGFILE=$BLUEPRINT_DIR/ctl_configure.log
CONF_FILE=$BLUEPRINT_DIR/conf.json

#Commons
USER_PATH=$(pwd)
USER_NAME=$(whoami)
CONTENT=$(find /home/)

#=========================================================================
#The print function goes to write log on stdout and on file
#=========================================================================
function print(){

   local line=$1

   echo -e $line | tee -a $LOGFILE

   if [[ $line == *ERROR* ]]
   then
     exit 1;
   fi

}

#=========================================================================
#The timestamp function returns timestamp using the following format:
#<YEAR>_<MONTH_DAY>_<HOUR>_<MINUTES>_<TIMEZONE>
#=========================================================================
timestamp(){

  TIMESTAMP=$(date +%Y_%m_%d_%H_%M)

}

#=========================================================================
#The initLog function goes to initialize the log file
#=========================================================================
function initLog(){

   echo "" > $LOGFILE
   timestamp
   print "########\b CTL BP Configuration \n Execution: $TIMESTAMP\n########"

}

#=========================================================================
#The restoreResolvConf function goes to restore the resolv.conf to be a symbolic link of /run/resolvconf/resolv.conf
#=========================================================================
function restoreResolvConf(){

#Restore resolv.conf as symbolic link to /etc/resolv.conf
rm /etc/resolv.conf
ln -s /run/resolvconf/resolv.conf /etc/resolv.conf

}

#=========================================================================
#The replace_line_statemachine function
#@Usage : replace_line_statemachine "<key>" "<key> = <value>" <FILE>
#@Example: replace_line_statemachine "DHT.enable" "DHT.enable = true" $CCC_DIR/conf/include/UI.properties
#=========================================================================
function replace_line_statemachine(){

  KEY=$1
  NEW_LINE=$2
  FILE=$3
  MODE=$4

  foundentry=false

  i=0
  while read -r line || [[ -n "$line" ]]; do
     i=$((i+1))
     if [[ $line == *$KEY* ]]
     then
       sudo sed -i "$i s@.*@$NEW_LINE@" $FILE
       foundentry=true
     fi

  done < $FILE

  if [[ $foundentry == false ]]
  then
    if [[ $MODE == "warn" ]]
    then
      print_both "WARN: unable to find $KEY entry on $FILE"
    else
      print_both "ERROR: unable to find $KEY entry on $FILE"
    fi
  fi
}

#=========================================================================
#The downloadRepo function download AEM requirements zip files
#=========================================================================
function downloadRepo(){

    local mode=$1

    print "Download chef repo archive"
    repoArchive="chefRepoPlatform.zip"
    nameMd5Entry=$(cat platformIndex.txt | grep $repoArchive)
    downloadAndCheckFile "$vpsURL/chef" $BLUEPRINT_DIR $nameMd5Entry

    print "Extract chef repo"
    unzip "$BLUEPRINT_DIR/$repoArchive" -d $BLUEPRINT_DIR | tee -a $LOGFILE
    rm "$BLUEPRINT_DIR/$repoArchive" | tee -a $LOGFILE

    print "Update cookbooks local repo with downloaded"
    cp -r $BLUEPRINT_DIR/cookbooks/* /var/chef/cache/cookbooks | tee -a $LOGFILE


}

#=========================================================================
#The downloadAndCheckFile function downloads a specific file on a target directory and check its md5
#============================== ==========================================
function downloadAndCheckFile(){

  local url=$1
  local targetDir=$2
  local fileAndMd5=$3

  fileName=$(echo ${fileAndMd5%:*})
  fileMd5=$(echo ${fileAndMd5##*:})

  targetFile=$url/$fileName
  print "Downloading $targetFile on $targetDir"
  wget "$targetFile" -P $targetDir

  print "Calculating md5 for download file $targetFile"
  calculatedMd5=$(md5sum $targetDir/$fileName | cut -d " " -f1)

  print "Calculated md5 is [$calculatedMd5]. Check if it is equals to [$fileMd5]"
  if [[ $calculatedMd5 == $fileMd5 ]]
  then
    print "File $targetFile downloaded correctly!"
  else
    print "ERROR: some problem has occurred on downloading file $targetFile. Downloaded file is corrupted. Md5 don't correspond. Check network and retry"
    exit 1;
  fi

}

#=========================================================================
#The updatePlaceholder function updates a placeholder on a specific file
#=========================================================================
function updatePlaceholder(){

    local parameter=$1
    local value=$2
    local file=$3

    print "#### Updating [$parameter] with value [$value] on file [$file] ( owner: $OWNER - password: $CCCUSER_PASSWORD ) "
    echo $CCCUSER_PASSWORD | sudo -Sp "" -u $OWNER sed -i "s/$parameter/$value/g" $file &>> $LOGFILE
    if [[ $? != 0 ]]
    then
      print "ERROR: unable to update $parameter on $file with value $value"
    fi

}

#=========================================================================
#The updateProperties function updates a key on a properties file
#=========================================================================
function updateProperties(){

   key=$1
   value=$2
   file=$3

   print "#### Updating key $key with value $value on file $file ####\nOwner: $OWNER\nPassword: $CCCUSER_PASSWORD"
   sed -i "/^$key.* =/c$key = $value" $file
   if [[ $? != 0 ]]
   then
     print "ERROR: unable to update key $key on $file with value $value"
   fi
}

#=========================================================================
#The configurePlatform functions goes to configure the platform instance parameters
#============================== ==========================================
function configurePlatform(){


if [[ -d /home/cccuser ]]
then
  timestamp
  print "#######\n Full Platform \n#######\ninternalIP=$internalIP\nuiID=$uiID\nExecuted by: $USER_NAME\nCurrent Path: $USER_PATH\nTimestamp: $TIMESTAMP\nHome dir Content=\n[\n$CONTENT\n]\n" > $LOGFILE

  for i in $(seq 1 5);
  do
    TIMESTAMP=$(date +%Y_%m_%d_%H_%M)
    print "Attempt n°$i - $TIMESTAMP" &>> $LOGFILE
    if [[ -f $CONF_FILE  ]]
    then

      updatePlaceholder "<CLUSTER_ID>" $clusterID $CONF_FILE
      updatePlaceholder "<PLATFORM_ID>" $platformID $CONF_FILE
      updatePlaceholder "<CONTROLLER_IP>" $controllerIP $CONF_FILE
      updatePlaceholder "<INTERNAL_IP>" $internalIP $CONF_FILE
      updatePlaceholder "<PUBLIC_IP>" $publicIP $CONF_FILE
      updatePlaceholder "<CCCUSER_PASSWORD>" $CCCUSER_PASSWORD $CONF_FILE

      replace_line_statemachine "replSet" "replSet = DefaultCloud" /etc/mongodb.conf

      FILE_CONTENT=$(cat $CONF_FILE)
      print "\nFile $CONF_FILE content is:\n[\n$FILE_CONTENT\n]\n" &>> $LOGFILE

      sudo chef-solo -c $BLUEPRINT_DIR/solo.rb -j $BLUEPRINT_DIR/conf.json | tee -a $LOGFILE
      if [[ $? != 0 ]]
      then
         print "ERROR: unable to execute chef-solo configuration. Check logs for details"
      fi

      cd $CCC_HOME

      echo $CCCUSER_PASSWORD | sudo -Sp "" -u $OWNER sudo chown cccuser:ccc -R $CCC_HOME | tee -a $LOGFILE

      echo $CCCUSER_PASSWORD | sudo -Sp "" -u $OWNER sudo chmod 775 -R $CCC_HOME | tee -a $LOGFILE


      echo $CCCUSER_PASSWORD | sudo -Sp "" -u $OWNER bash $CCC_HOME/engine.sh stop | tee -a $LOGFILE

      sleep 2

      echo $CCCUSER_PASSWORD | sudo -Sp "" -u $OWNER bash $CCC_HOME/hard.sh start | tee -a $LOGFILE

      sleep 1

      echo $CCCUSER_PASSWORD | sudo -Sp "" -u $OWNER bash $CCC_HOME/engine.sh start | tee -a $LOGFILE

      sleep 5

      sudo rm /etc/rc1.d/S99configure_platform.sh
      sudo rm /etc/rc2.d/S99configure_platform.sh
      sudo rm /etc/rc3.d/S99configure_platform.sh
      sudo rm /etc/init.d/configure_platform.sh

      exit 0;

    else
      print "File $CONF_FILE not found. Wait 1 minute and retry"
    fi
    sleep 1m
  done

  print "ERROR: 5 minutes passed. No file found" &>> $LOGFILE
  exit 3;
else
  exit 5;
fi

}

# Restore resolv.conf
#===================
restoreResolvConf

# Download AEM Requirements from VPS
#===================
downloadRepo

# Configure Platform
#===================
configurePlatform
