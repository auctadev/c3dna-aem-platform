#!/usr/bin/env python

import re
import os
import os.path
import sys
import time
import shutil
import subprocess

TARGET_DISK=sys.argv[1]


status_timestamps = {}
def Status(msg,status="New"):
    if status=='New':
        print "Beginning %s" % msg
        status_timestamps[msg] = time.time()
    else:
        print "%s %s... (%ss)" % (status,msg,int(time.time()-status_timestamps[msg]))


#
# System pre-reqs
Status("system package install")
subprocess.Popen("apt-get -qqy install lvm2 mdadm",shell=True).wait()
Status("system package install","Completed")


#
# Mount disk and begin customizations
#
# Scan and assemble raid volumes
subprocess.Popen("mdadm --detail --scan >> /etc/mdadm/mdadm.conf", shell=True, stdout=subprocess.PIPE).communicate()

Status("mounting image")
subprocess.Popen("partprobe %s" % TARGET_DISK,shell=True).wait() # system reload partition tables


#
# Build list of viable partitions
#
partitions_to_mount=[]
parted_out, parted_err = subprocess.Popen("parted -m %s -s print | tail -n +3" % TARGET_DISK,shell=True,stdout=subprocess.PIPE).communicate()
if len(parted_out)==0:
    # openvpn uses entire disk
    partitions_to_mount.append("mount %s /mnt" % TARGET_DISK)    # No partitions - using whole disk?

for parted_line in parted_out.split("\n"):
    cols = parted_line.split(":")
    if len(cols)<=1:  continue
    partition_num = cols[0]
    partition_type = cols[4]

    if 'raid;' in parted_line.lower():
        idx = int(partition_num) - 1
        if not os.path.exists("/dev/md%s" % idx):
            assemble_out, assemble_err = subprocess.Popen("mdadm --assemble --run /dev/md%s" % idx , shell=True, stdout=subprocess.PIPE).communicate()
            print assemble_out, assemble_err
        partitions_to_mount.append("mount /dev/md%s /mnt" % (idx))
    elif re.search("lvm",parted_line):
        ## TODO
        #dprobe dm-mod
        subprocess.Popen("vgchange -ay",shell=True)
        lvscan_out, lvscan_err = subprocess.Popen("lvscan | awk '{print $2}' | perl -p -e \"s/'//g\"",shell=True,stdout=subprocess.PIPE).communicate()
        for lv_part in lvscan_out.split("\n"):
            if not len(lv_part):  continue
            file_out, file_err = subprocess.Popen("file -sL %s" % lv_part,shell=True,stdout=subprocess.PIPE).communicate()
            if re.search("ext[234]|reiserfs",file_out):
                # direct mountable partitions
                partitions_to_mount.append("mount %s /mnt" % lv_part)
            elif partition_type in ("swap"):
                ## Ignore these types
                pass
            else:
                print "Unknown partition type '%s\\%s' on %s%s\n" % (partition_type,file_out,TARGET_DISK,partition_num)
    elif partition_type in ("ext2","ext3","ext4","reiserfs", "xfs"):
        # direct mountable partitions
        partitions_to_mount.append("mount %s%s /mnt" % (TARGET_DISK,partition_num))
    elif partition_type in ("swap","fat16"):
        ## Ignore these types
        pass
    else:
        print "Unknown partition type '%s' on %s%s\n" % (partition_type,TARGET_DISK,partition_num)

#
# Proess each viable partition
#
configs_set = {}

for mount_cmd in partitions_to_mount:
    subprocess.Popen("umount /mnt",shell=True).wait()

    print "Executing: %s" % mount_cmd

    p = subprocess.Popen(mount_cmd,shell=True)
    err = p.wait()
    if err>0:
        print "Error mounting partition with command '%s'\n" % mount_cmd

    # Execute pre-boot script
    #subprocess.Popen("cd /mnt && %s/preboot_script.sh" % os.getcwd(),shell=True).wait()

    # Proceed only if we have access to etc - assume this means a root partition
    if not os.path.exists("/mnt/etc"):  continue

    # Disable cloud-config
    subprocess.Popen("rm -f /mnt/etc/init/cloud-*",shell=True).wait()

    # Set DNS #
    subprocess.Popen("rm -f /mnt/etc/resolv.conf",shell=True).wait()
    subprocess.Popen("cp -Hf /etc/resolv.conf /mnt/etc/resolv.conf",shell=True).wait()

    # Copy sysadmin scripts
    # TODO - only if we're within a specific set of operating systems?  And only
    #        if we are at the root partition level.
    subprocess.Popen("cp -Rp /sysadmin /mnt/",shell=True).wait()

    # Set hostname
    subprocess.Popen("rm -f /mnt/etc/hostname",shell=True).wait()
    subprocess.Popen("cp /etc/hostname /mnt/etc/hostname",shell=True).wait()

    # Get network variables
    nw_mac = subprocess.check_output("ifconfig eth0 | grep HWaddr | awk '{print $5}'",shell=True).strip()
    nw_ipaddr = subprocess.check_output("ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'",shell=True).strip()
    nw_netmask = subprocess.check_output("ifconfig eth0 | grep 'Mask:' | awk '{print $4}' | cut -d: -f2",shell=True).strip()
    nw_broadcast = subprocess.check_output("ifconfig eth0 | grep 'Bcast:' | awk '{print $3}' | cut -d: -f2",shell=True).strip()
    nw_gw = subprocess.check_output("netstat -nr | grep \"^0.0.0.0\" | awk '{print $2}'",shell=True).strip()
    nw_hostname = subprocess.check_output("hostname",shell=True).strip()
    nw_network = subprocess.check_output("route | tail -1 | awk '{print $1}'",shell=True).strip()
    subprocess.Popen("echo '%s %s' >> /mnt/etc/hosts" % (nw_ipaddr, nw_hostname),shell=True).wait()

    # Enable networking in sysconfig for any system supporting
    if os.path.exists("/mnt/etc/sysconfig/network"):
        with open("/mnt/etc/sysconfig/network", 'w') as fh:
            print >> fh, "NETWORKING=yes"

    #rcfile = None

    # OS Specific config
    # SuSe Type
    if os.path.exists("/mnt/etc/SuSE-release"):
        print "*** SuSE!"
        configs_set['network'] = True
        if os.path.exists("/mnt/etc/sysconfig/network/ifcfg.template"):  os.remove("/mnt/etc/sysconfig/network/ifcfg.template")
        if os.path.exists("/mnt/etc/sysconfig/network/config"):  os.remove("/mnt/etc/sysconfig/network/config")
        #rcfile = "/mnt/etc/rc.d/after.local"
        subprocess.Popen("cd /mnt && tar xfz %s/sysadmin.suse.tar.gz" % os.getcwd(),shell=True).wait()
        subprocess.Popen("cd /mnt/etc/sysconfig/network && rm -f `ls ifcfg-* ifroute-* | grep -v lo`",shell=True).wait()
        for nic in ("lan0","eth0"):
            with open("/mnt/etc/sysconfig/network/ifroute-%s" % nic,"w") as fh:
                print >> fh, '# Destination     Dummy/Gateway     Netmask      Device'
                print >> fh, 'default %s - %s' % (nw_gw, nic)
            with open("/mnt/etc/sysconfig/network/ifcfg-%s" % nic,"w") as fh:
                print >> fh, 'STARTMODE=auto'
                print >> fh, 'BOOTPROTO=static'
                print >> fh, 'IPADDR=%s' % nw_ipaddr
                print >> fh, 'NETMASK=%s' % nw_netmask
                print >> fh, 'BROADCAST=%s' % nw_broadcast
                print >> fh, 'NETWORK=%s' % nw_network

    # RHEL Type
    elif os.path.exists("/mnt/etc/redhat-release") or \
        os.path.exists("/mnt/etc/rpm/platform") or \
        os.path.exists("/mnt/etc/sysconfig/network-scripts/"):
        print "*** RPM!"
        configs_set['network'] = True
        #rcfile = "/mnt/etc/rc.d/rc.local"
        subprocess.Popen("cd /mnt && tar xfz %s/sysadmin.redhat.tar.gz" % os.getcwd(),shell=True).wait()
        with open("/mnt/etc/sysconfig/network-scripts/ifcfg-eth0","w") as fh:
            print >> fh, 'DEVICE=eth0'
            print >> fh, 'TYPE=Ethernet'
            print >> fh, 'BOOTPROTO=none'
            print >> fh, 'ONBOOT=yes'
            print >> fh, 'HWADDR=%s' % nw_mac
            print >> fh, 'IPADDR=%s' % nw_ipaddr
            print >> fh, 'NETMASK=%s' % nw_netmask
            print >> fh, 'GATEWAY=%s' % nw_gw
            print >> fh, 'DNS1=172.17.1.26'
            print >> fh, 'DNS2=172.17.1.27'

    # DEB Type
    elif os.path.exists("/mnt/etc/debian_version") or os.path.exists("/mnt/etc/network/interfaces"):
        print "*** DEB!"
        configs_set['network'] = True
        #rcfile = "/mnt/etc/rc3.d/S99rc.local"
        subprocess.Popen("cd /mnt && tar xfz %s/sysadmin.debian.tar.gz" % os.getcwd(),shell=True).wait()
        with open("/mnt/etc/network/interfaces","w") as fh:
            print >> fh, 'iface lo inet loopback'
            print >> fh, 'auto lo'
            print >> fh, ''
            print >> fh, 'auto eth0'
            print >> fh, 'iface eth0 inet static'
            print >> fh, 'address %s' % nw_ipaddr
            print >> fh, 'netmask %s' % nw_netmask
            print >> fh, 'up route add default gw %s' % nw_gw
            print >> fh, 'dns-search %s' % nw_hostname
            print >> fh, 'dns-nameservers 172.17.1.26 172.17.1.27'

    # Gentoo Type
    elif os.path.exists("/mnt/etc/gentoo-release"):
        print "*** GENTOO!"
        configs_set['network'] = True
        subprocess.Popen("cd /mnt && tar xfz %s/sysadmin.debian.tar.gz" % os.getcwd(),shell=True).wait()
        for path in ['/mnt/etc/conf.d/net.eth0', '/mnt/etc/conf.d/net']:
            if not os.path.exists(path):
                continue
            with open(path,"w") as fh:
                print >> fh, 'config_eth0=( "%s netmask %s broadcast %s" )' % (nw_ipaddr, nw_netmask, nw_broadcast)
                print >> fh, 'routes_eth0=( "default via %s" )' % (nw_gw)
                print >> fh, 'dns_eth0="172.17.1.26 172.17.1.27"'

    # Custom
    elif os.path.exists("/mnt/etc/network/ifconfig.eth0"):
        configs_set['network'] = True
        with open("/mnt/etc/network/ifconfig.eth0","w") as fh:
            print >> fh, 'DEVICE=eth0'
            print >> fh, 'ONBOOT=yes'
            print >> fh, 'SERVICE=ipv4-static'
            print >> fh, 'IP=%s' % nw_ipaddr
            print >> fh, 'NETMASK=%s' % nw_netmask
            print >> fh, 'GATEWAY=%s' % nw_gw
            print >> fh, 'BROADCAST=%s' % nw_broadcast
            print >> fh, 'DNS1=172.17.1.26'
            print >> fh, 'DNS2=172.17.1.27'

    # TODO: BSD based

    else:
        print "ERROR: Unable to identify OS"
        sys.exit(1)


    # Copy post-boot script into position
    #if rcfile:
    #    try:
    #        shutil.copy("postboot_script_wrapper.sh","/mnt/etc/")
    #        shutil.copy("postboot_script.sh","/mnt/etc/")
    #        subprocess.Popen("chmod +x %s" % rcfile,shell=True).wait();
    #        with open(rcfile,"a") as fh:
    #            fh.write("""\n/etc/postboot_script_wrapper.sh\n""")
    #    except:
    #        pass


    # Set root password
    if os.path.exists("/mnt/etc/shadow"):
        subprocess.Popen("grep ^root /etc/shadow > /tmp/shadow",shell=True).wait()
        subprocess.Popen("grep -v ^root /mnt/etc/shadow >> /tmp/shadow",shell=True).wait()
        subprocess.Popen("mv -f /tmp/shadow /mnt/etc/shadow",shell=True).wait()

    # Enable ssh at boot - assumes default runlevel 3
    # TODO - does not catch SuSe Linux, they have a different structure
    if os.path.exists("/mnt/etc/rc3.d") and subprocess.Popen("ls -l /mnt/etc/rc3.d | grep ssh>/dev/null 2>&1",shell=True).wait():
        subprocess.Popen("cd /mnt/etc; ln -s ../`ls init.d/*ssh*|head -1` rc3.d/S75ssh",shell=True).wait()

    # Enable root ssh login
    if os.path.exists("/mnt/etc/ssh/sshd_config"):
        configs_set['ssh'] = True
        subprocess.Popen("rm -f /mnt/etc/ssh/ssh_host_*",shell=True).wait()
        # regenerate new host keys into target volume
        # (c3dna images were not regenerating on boot)
        subprocess.Popen("/usr/bin/ssh-keygen -f /mnt/etc/ssh/ssh_host_rsa_key -b 2048 -N '' -t rsa < /dev/null > /dev/null 2> /dev/null",shell=True).wait()
        subprocess.Popen("/usr/bin/ssh-keygen -f /mnt/etc/ssh/ssh_host_dsa_key -b 1024 -N '' -t dsa < /dev/null > /dev/null 2> /dev/null",shell=True).wait()
        subprocess.Popen("/usr/bin/ssh-keygen -f /mnt/etc/ssh/ssh_host_ecdsa_key -N '' -t ecdsa < /dev/null > /dev/null 2> /dev/null",shell=True).wait()

        subprocess.Popen("perl -p -i -e 's/^Port.*/Port 22/gi' /mnt/etc/ssh/sshd_config",shell=True).wait()
        subprocess.Popen("perl -p -i -e 's/^PermitRootLogin/#PermitRootLogin/gi' /mnt/etc/ssh/sshd_config",shell=True).wait()
        subprocess.Popen("echo 'PermitRootLogin yes' >> /mnt/etc/ssh/sshd_config",shell=True).wait()
        subprocess.Popen("perl -p -i -e 's/^\s*PasswordAuthentication.*/PasswordAuthentication yes/gi' /mnt/etc/ssh/sshd_config",shell=True).wait()

subprocess.Popen("umount /mnt",shell=True).wait()


# Alert if configs not set
Status("mounting image","Complete")

if not configs_set:
    print "\n===============\nWARNING! No configuration set in target systems. Proceeding anyway\n\n"
