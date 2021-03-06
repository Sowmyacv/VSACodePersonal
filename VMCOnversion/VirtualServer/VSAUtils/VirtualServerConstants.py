"""
Main file  for declaring all constants needed for  VSA Automation
"""

import os
from enum import Enum

APP_TYPE = 106
Ip_regex = "(^169\.)"
AppName = "VIRTUAL SERVER"
AutomationAppType = "Q_VIRTUAL_SERVER"
PseuDoclientPropList = 'Virtual Server Host', 'Virtual Server User'
vm_pattern_names = {'[OS]': 'GuestOS',
                    '[DNS]': 'server_name',
                    '[DS]': 'Datastore',
                    '[VM]': 'vm_name',
                    '[HN]': 'server_clientname'}
content_types = {'Virtual Machine': "[VM]", '1': "[HN]"}
disk_count_command = "(get-disk | select number, size).count"


class hypervisor_type(Enum):
    """
    Enum class for declaring allt he Hypervior types
    """

    VIRTUAL_CENTER = "VMware"
    MS_VIRTUAL_SERVER = "Hyper-V"
    AZURE = "Azure"
    AZURE_V2 = "Azure Resource Manager"
    Fusion_Compute = "FusionCompute"


def on_premise_hypervisor(instance_name):
    """
    :param instance_name:  Instance name of the Instance need to be checked
    :return:
        True if the Hypervisor is on premise else false

    """
    vendor = {"vmware": True, 'hyper-v': True, 'Azure Resource Manager': False, 'Azure': False}
    return vendor[instance_name]


def is_dynamic_type(vm_name, vm_type):
    """
    check whether the VM string passed contain dynamic VM

    Args:
            vm_name: name of the VM eg: VM1, VM*
            vm_type  : Type of the Input like VM name, HostName

    Returns:
            Bool value based on dynamic or not
    """

    is_not_dynamic = False
    vm_name_type = ['9', '10']
    if vm_type in vm_name_type:
        if '*' not in vm_name:
            is_not_dynamic = True

    return is_not_dynamic


def is_windows(os_name):
    """
    check for the os in Windows or Unix flavours

    Args:
    os_name - Nmae of the OS

    returns:
            bool value based whether the OS is windows or not
    """
    return bool(os_name == "Windows")


def get_live_browse_db_path(base_dir):
    """
    Get the db path for the live browse
    Args:
            base_dir - base directory where the contentstore is installed

    return:


    """

    return os.path.join(base_dir, "PseudoMount", "Persistent", "PseudoMountDB")


def get_live_browse_mount_path(base_dir, GUID, os_name):
    """
    Get the devices mount path for the live browse
    Args:
            base_dir - base directory where the contentstore is installed

            GUID - GUID of the VM browsed

    return:
        devices mount path for the live browse

    """

    if os_name == "Windows":
        return os.path.join(base_dir, "PseudoMount", "Persistent", "PseudoDevices", GUID)

    else:
        return "/opt/FBR/cvblk_mounts"


def get_folder_to_be_compared(folder_name, _driveletter):
    """
    return the default folder restore path
    Args:
            FolderName - name of the folder
            _driveletter- drive letter where data was copied

    """

    if _driveletter is None:
        return "C:\\TestData\\{0}\\".format(folder_name)
    else:

        return os.path.join(_driveletter, "\\" + folder_name, "TestData")


def BrowseFilters():
    """
    :return: Browse Filters for XML
    """
    return r"""&lt;?xml version='1.0' encoding='UTF-8'?&gt;&lt;databrowse_Query type="0"
    queryId="0"&gt;&lt;dataParam&gt;&lt;sortParam ascending="1"&gt;&lt;sortBy val="38"
    /&gt;&lt;sortBy val="0" /&gt;&lt;/sortParam&gt;&lt;paging firstNode="0" pageSize="100"
    skipNode="0" /&gt;&lt;/dataParam&gt;&lt;/databrowse_Query&gt;"""
