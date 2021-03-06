# -*- coding: utf-8 -*-

# --------------------------------------------------------------------------
# Copyright Commvault Systems, Inc.
# See LICENSE.txt in the project root for
# license information.
# --------------------------------------------------------------------------

"""Main file that does all operations on VM

classes defined:
    Base class:
        HypervisorVM- Act as base class for all VM operations

    Inherited class:
        HyperVVM - Does all operations on Hyper-V VM

    Methods:

        get_drive_list()    - get all the drive list associated with VM

        power_off()            - power off the VM

        power_on()            -power on the VM

        delete_vm()            - delete the VM

        update_vm_info()    - updates the VM info
    """

import os
import re
import time
from abc import ABCMeta, abstractmethod
from AutomationUtils import logger
from AutomationUtils import machine
from time import sleep
from . import VirtualServerUtils, VirtualServerConstants, FusionComputeServices
import configparser


class HypervisorVM(object):
    """
    Main class for performing operations on Hyper-V VM
    """
    __metaclass__ = ABCMeta

    def __new__(cls, Hvobj, vm_name):
        """
        Initialize VM object based on the Hypervisor of the VM
        """

        hv_type = VirtualServerConstants.hypervisor_type
        if Hvobj.instance_type.lower() == hv_type.MS_VIRTUAL_SERVER.value.lower():
            return object.__new__(HyperVVM)
        elif Hvobj.instance_type.lower() == hv_type.VIRTUAL_CENTER.value.lower():
            return object.__new__(VmwareVM)
        elif Hvobj.instance_type == hv_type.AZURE_V2.value.lower():
            return object.__new__(AzureVM)
        elif Hvobj.instance_type.lower() == hv_type.Fusion_Compute.value.lower():
            return object.__new__(FusionComputeVM)
        elif Hvobj.instance_type.lower() == hv_type.ORACLE_VM.value.lower():
            return object.__new__(OracleVMHelper)

    def __init__(self, Hvobj, vm_name):
        """
        Initialize the VM initialization properties
        """
        self.vm_name = vm_name
        self.Hvobj = Hvobj
        self.commcell = self.Hvobj.commcell
        self.server_name = Hvobj.server_host_name
        self.host_user_name = Hvobj.user_name
        self.host_password = Hvobj.password
        self.log = logger.get_log()
        self.instance_type = Hvobj.instance_type
        self.utils_path = VirtualServerUtils.UTILS_PATH
        self.host_machine = self.Hvobj.machine
        self.GuestOS = None
        self.IP = None
        self._DriveList = None
        self._user_name = None
        self._password = None
        self.config = configparser.ConfigParser()
        self._drives = None
        self.GuestOS = None
        self.machine = None
        self._preserve_level = 1
        self.DiskType = None
        self.DiskList = []

    @property
    def drive_list(self):
        """
        Returns the drive list for the VM. This is read only property
        """
        if self._drives is None:
            self.get_drive_list()
        return self._drives

    @property
    def user_name(self):
        """gets the user name of the Vm prefixed with the vm name to avoid conflict.
        It is a read only attribute"""

        return self._user_name

    @user_name.setter
    def user_name(self, value):
        """sets the username of the vm"""

        self._user_name = value

    @property
    def password(self):
        """gets the user name of the Vm . It is a read only attribute"""

        return self._password

    @password.setter
    def password(self, value):
        """sets the password of the vm"""

        self._password = value

    @property
    def vm_hostname(self):
        """gets the vm hostname as IP (if available or vm name). It is a read only attribute"""

        if self.IP:
            return self.IP

        return self.vm_name

    @property
    def vm_guest_os(self):
        """gets the VM Guest OS . it is read only attribute"""
        return self.machine

    @vm_guest_os.setter
    def vm_guest_os(self, value):
        self._set_credentials(value)

    @property
    def preserve_level(self):
        """gets the default preserve level of Guest OS. it is read only attribute"""
        if self.GuestOS == "Windows":
            self._preserve_level = 0
        else:
            self._preserve_level = 1

        return self._preserve_level

    # just to reduce redirection

    def _set_credentials(self, os_name):
        """
        set the credentials for VM by reading the config INI file
        """

        config_ini_file = os.path.join(os.path.dirname(__file__), "VMConfig.ini")
        self.config.read(config_ini_file)
        sections = self.config.get(os_name, "username")
        user_list = sections.split(",")
        incorrect_usernames = []
        for each_user in user_list:
            self.user_name = each_user.split(":")[0]
            self.password = VirtualServerUtils.decode_password(each_user.split(":")[1])
            try:
                vm_machine = machine.Machine(self.vm_hostname,
                                             username=self.user_name,
                                             password=self.password)
                if vm_machine:
                    self.machine = vm_machine
                    return
            except:
                incorrect_usernames.append(each_user.split(":")[0])

        self.log.exception("Could not create Machine object! The following user names are "
                           "incorrect: {0}".format(incorrect_usernames))

    def get_drive_list(self):
        """
        Returns the drive list for the VM
        """
        try:
            _temp_drive_letter = {}
            storage_details = self.machine.get_storage_details()

            if self.GuestOS == "Windows":
                _drive_regex = "^[a-zA-Z]$"
                for _drive, _size in storage_details.items():
                    if re.match(_drive_regex, _drive):
                        _drive = _drive + ":"
                        _temp_drive_letter[_drive.split(":")[0]] = _drive

            else:
                index = 1
                for _drive, _volume in storage_details.items():
                    if "/dev/sd" in _drive:
                        _temp_drive_letter["MountDir-" + str(index)] = _volume["mountpoint"]
                        index = index + 1

                    if "dev/mapper" in _drive:
                        _volume_name = _drive.split("/")[-1]
                        _temp_drive_letter[_volume_name] = _volume["mountpoint"]

            self._drives = _temp_drive_letter
            if not self._drives:
                raise Exception("Failed to Get Volume Details for the VM")

        except Exception as err:
            self.log.exception(
                "An Exception Occurred in Getting the Volume Info for the VM {0}".format(err))
            return False

    @abstractmethod
    def power_off(self):
        """
        power off the VM.

        return:
                True - when power off is successfull

        Exception:
                When power off failed

        """
        self.log.info("Power off the VM")

    @abstractmethod
    def power_on(self):
        """
        power on the VM.

        return:
                True - when power on is successful

        Exception:
                When power on failed

        """
        self.log.info("Power on the VM")

    @abstractmethod
    def delete_vm(self):
        """
        power on the VM.

        return:
                True - when delete is successful

                False - when delete failed
        """
        self.log.info("Delete the VM")

    @abstractmethod
    def update_vm_info(self):
        """
        fetches all the properties of the VM

        Args:
                should have code for two possibilties

                Basic - Basic properties of VM like HostName,GUID,Nic
                        especially the properties with which VM can be added as dynamic content

                All   - All the possible properties of the VM

                Set the property VMGuestOS for creating OS Object

                all the property need to be set as class variable

        exception:
                if failed to get all the properties of the VM
        """
        self.log.info("Update the VMinfo of the VM")


class HyperVVM(HypervisorVM):
    """
    This is the main file for all  Hyper-V VM operations
    """

    def __init__(self, hv_obj, vm_name):
        """
        Initialization of hyper-v vm properties

        _get_vm_host()            - get the host of the VM among the servers list

        _get_vm_info()            - get the particular  information of VM

        _get_disk_list()        - gets the disk list opff the VM

        _merge_vhd()            - Merge the VHD with its snapshots

        mount_vhd()                - Mount the Vhd/VHDX and return the drive letter

        un_mount_vhd()            - Unmount the VHD mounted provided the path

        _get_disk_in_controller()- get the disk in controller attached

        _get_disk_path_from_pattern() - get the list of disk from pattern

        power_off()            - power off the VM

        power_on()            -power on the VM

        delete_vm()            - delete the VM

        update_vm_info()    - updates the VM info

        """

        super(HyperVVM, self).__init__(hv_obj, vm_name)
        self.server_client_name = hv_obj.server_list
        self.vmserver_host_name = self.server_name

        self.vm_props_file = "GetHypervProps.ps1"
        self.vm_operation_file = "HyperVOperation.ps1"

        self.prop_dict = {
            "server_name": self.vmserver_host_name,
            "extra_args": "$null",
            "vm_name": self.vm_name
        }
        self.vmserver_host_name = self.vm_host

        self.host_machine = machine.Machine(
            self.server_client_name, self.commcell)

        self.operation_dict = {
            "server_name": self.vmserver_host_name,
            "extra_args": "$null",
            "vm_name": self.vm_name,
            "vhd_name": "$null"
        }
        self.GUID = None
        self.IP = None
        self.GuestOS = None
        self.HostName = None
        self._disk_list = None
        self.disk_dict = None
        self.DiskPath = None
        self.update_vm_info()

    @property
    def disk_list(self):
        """to fetch the disk in the VM
        Return:
            disk_list   (list)- list of disk in VM
            e.g:[ide0-0-test1.vhdx]
        """
        self.disk_dict = self._get_disk_list
        if self.disk_dict:
            self._disk_list = self.disk_dict.keys()

        else:
            self._disk_list = []

        return self._disk_list

    @property
    def vm_host(self):
        """
        get the Host of the VM

        Return:
            vm_host     (str)- VM Host of the VM
        """
        if not isinstance(self.server_client_name, list):
            server_list = [self.server_client_name]
        else:
            server_list = self.server_client_name

        _vm_host = self._get_vm_host(server_list)
        self.server_client_name = _vm_host
        client = self.commcell.clients.get(_vm_host)
        self.prop_dict["server_name"] = client.client_hostname
        return client.client_hostname

    def update_vm_info(self, prop='Basic', os_info=False):
        """
        fetches all the properties of the VM

        Args:
                should have code for two possibilties

                Basic - Basic properties of VM like HostName,
                            especially the properties with which VM can be added as dynamic content

                All   - All the possible properties of the VM

                os_info - Set the property VMGuestOS for creating OS Object

        exception:
                if failed to get all the properties of the VM
        """

        try:
            self._get_vm_info(prop)
            if os_info or prop == 'All':
                self.vm_guest_os = self.GuestOS
                self.get_drive_list()

        except Exception as err:
            self.log.exception("Failed to Get  the VM Properties of the VM")
            raise Exception(err)

    def _get_vm_host(self, server_list):
        """
        from the list of
        """
        try:
            server_name = server_list[0]
            for _each_server in server_list:
                client = self.commcell.clients.get(_each_server)
                _ps_path = os.path.join(self.utils_path, self.vm_props_file)
                self.prop_dict["server_name"] = client.client_hostname
                self.prop_dict["property"] = "GetAllVM"
                output = self.host_machine._execute_script(_ps_path, self.prop_dict)
                _psoutput = output.output
                _stdout = _psoutput.rsplit("=", 1)[1]
                _stdout = _stdout.strip()
                _temp_vm_list = _stdout.split(",")
                for each_vm in _temp_vm_list:
                    if each_vm != "":
                        each_vm = each_vm.strip()
                        if re.match("^[A-Za-z0-9_-]*$", each_vm):
                            if each_vm == self.vm_name:
                                server_name = _each_server
                                break
                            else:
                                continue
                        else:
                            self.log.info(
                                "Unicode VM are not supported for now")

            return server_name

        except Exception as err:
            self.log.exception(
                "An exception occurred while getting all Vms from Hypervisor")
            raise Exception(err)

    def _get_vm_info(self, prop, extra_args="$null"):
        """
        get the basic or all or specific properties of VM

        Args:
                prop         -    basic, All or specific property like Memory

                ExtraArgs    - Extra arguments needed for property listed by ","

        exception:
                if failed to get all the properties of the VM

        """
        try:

            self.log.info(
                "Collecting all the VM properties for VM %s" % self.vm_name)
            _ps_path = os.path.join(self.utils_path, self.vm_props_file)
            self.prop_dict["property"] = prop
            self.prop_dict["extra_args"] = extra_args
            output = self.host_machine._execute_script(_ps_path, self.prop_dict)
            _stdout = output.output
            self.log.info("output of all vm prop is {0}".format(_stdout))
            if _stdout != "":
                if ";" in _stdout:
                    stdlines = _stdout.split(';')
                else:
                    stdlines = [_stdout.strip()]
                for _each_prop in stdlines:
                    key = _each_prop.split("=")[0]
                    val = _each_prop.split("=")[1]
                    val = val.strip()
                    if val == "":
                        val = None
                    setattr(self, key, val)

        except Exception as err:
            self.log.exception("Failed to Get all the VM Properties of the VM")
            raise Exception(err)

    @property
    def _get_disk_list(self):
        """
        get the list of disk in the VM

        Returns:
                _disk_dict : with keys as disk name and value as snapshot associated with diskname

                _diks_dict = {
                        "test1.vhdx":["test1_184BDFE9-1DF5-4097-8BC3-06128C581C42.avhdx",
                        "test1_184BDEF9-1DF5-4097-8BC3-06128C581c82.avhdx"]
                }

        """
        try:
            _disk_dict = {}
            if self.DiskPath is None:
                self._get_vm_info('DiskPath')

            if self.DiskPath is not None:
                if "," in self.DiskPath:
                    temp_list = self.DiskPath.split(",")

                else:
                    temp_list = [self.DiskPath]

                for each_disk_list in temp_list:
                    final_disk = (each_disk_list.split("::")[0]).strip()
                    _temp_disk_list = (each_disk_list.split("::")[1]).strip()
                    if " " in _temp_disk_list:
                        _disk_list = _temp_disk_list.split(" ")
                    else:
                        _disk_list = [_temp_disk_list]

                    _disk_dict[final_disk] = _disk_list

            else:
                self.log.info("Cannot collect Disk  Path information")

            return _disk_dict
        except Exception as err:
            self.log.exception("Failed to Get all the VM Properties of the VM")
            raise Exception(err)

    def _merge_vhd(self, vhd_name):
        """
        merge all the snapshot disk with base disk

        Args:
                vhd_name (str)    - name of the VHD which all snapshots has to be merged

        Return:
                disk_merge     (bool)    - true when merge is success
                                                          False when Merge fails

                base_vhd_name    (str)- base Vhd Name after merging snapshots

        """
        try:
            disk_merge = True
            do_merge = False
            _base_vhd_name = None

            for each_key in self.disk_dict.keys():
                if(os.path.basename(vhd_name)) == (os.path.basename(each_key)):
                    _base_src_vhd_name = (self.disk_dict[each_key])[-1]
                    _base_vhd_name = os.path.join(os.path.dirname(
                        vhd_name), os.path.basename(_base_src_vhd_name))
                    do_merge = True
                    break

            if do_merge:
                _ps_path = os.path.join(
                    self.utils_path, self.vm_operation_file)
                self.operation_dict["operation"] = "Merge"
                self.operation_dict["extra_args"] = vhd_name, _base_vhd_name
                output = self.host_machine._execute_script(_ps_path, self.operation_dict)
                _stdout = output.output
                if _stdout != 0:
                    self.log.info(
                        "Failed to marge disk but still will try to mount it")
                    disk_merge = False

            else:
                self.log.info(
                    "Cannot find the disk at all please check the browse")
                return False, None

            return disk_merge, _base_vhd_name

        except Exception as err:
            self.log.exception("Failed to Get all the VM Properties of the VM")
            raise Exception(err)

    def mount_vhd(self, vhd_name, destination_client=None):
        """
        Mount the VHD provided

        Args:
                vhd_name            (str)    - vhd name that has to be mounted


                destination_client  (obj)   - client where the disk to be mounted are located

        returns:
                _drive_letter_list    (list)    - List of drive letters that is retuned after mount
                                                        [A:,D:]

                                                        Fasle    - if failed to mount
        """
        try:
            _drive_letter_list = []

            if not destination_client:
                destination_client = self.host_machine

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "MountVHD"
            self.operation_dict["vhd_name"] = vhd_name.strip()
            output = destination_client._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output

            if "Success" in _stdout:
                _stdout = _stdout.split("\n")
                for line in _stdout:
                    if "DriveLetter" in line:
                        _drive_letter = line.split("=")[1]
                        _drive_letter = _drive_letter.strip()
                        if "," in _drive_letter:
                            _temp_drive_letter_list = _drive_letter.split(",")
                        else:
                            _temp_drive_letter_list = [_drive_letter]

                for each_drive in _temp_drive_letter_list:
                    if each_drive:
                        each_drive = each_drive + ":"
                        _drive_letter_list.append(each_drive)

                for each_drive in _drive_letter_list:
                    self.log.info("drive letter %s" % each_drive)

                return _drive_letter_list
            else:
                self.log.error("The error occurred %s" % _stdout)
                return False

        except Exception as err:
            self.log.exception("Exception in MountVM")
            raise Exception("Exception in MountVM:{0}".format(err))

    def un_mount_vhd(self, vhd_name):
        """
        Un-mount the vhd name provided

        args:
                vhd_name : vhd needs to be unmounted

        return:
                True    (bool)         - if vhd is unmounted

        Exception:
                if fails to unmount

        """

        try:
            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "UnMountVHD"
            self.operation_dict["vhd_name"] = vhd_name.strip()
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if "Success" in _stdout:
                return True
            else:
                self.log.error("The error occurred %s" % _stdout)
                raise Exception("Exception in UnMountVM")

        except Exception as err:
            self.log.exception("Exception in UnMountVM")
            raise Exception("Exception in UnMountVM:{0}".format(err))

    def power_on(self):
        """
        power on the VM.

        return:
                True - when power on is successful

        Exception:
                When power on failed

        """

        try:

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "PowerOn"
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if "Success" in _stdout:
                return True
            else:
                self.log.error("The error occurred %s" % _stdout)
                raise Exception("Exception in PowerOn")

        except Exception as err:
            self.log.exception("Exception in PowerOn")
            raise Exception("Exception in PowerOn:{0}".format(err))

    def power_off(self):
        """
        power off the VM.

        return:
                True - when power off is successful

        Exception:
                When power off failed

        """

        try:

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "PowerOff"
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output

            if "Success" in _stdout:
                return True
            else:
                self.log.error("The error occurred %s" % _stdout)
                raise Exception("Exception in PowerOff")

        except Exception as err:
            self.log.exception("Exception in PowerOff")
            raise Exception("Exception in PowerOff:" + str(err))

    def delete_vm(self, vm_name=None):
        """
        Delete the VM.

        return:
                True - when Delete  is successful
                False -  when delete is failed

        """

        try:

            if vm_name is None:
                vm_name = self.vm_name

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "Delete"
            self.operation_dict["vm_name"] = vm_name
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if "Success" in _stdout:
                return True
            else:
                self.log.error("The error occurred %s" % _stdout)
                return False

        except Exception as err:
            self.log.exception("Exception in DeleteVM {0}".format(err))
            return False

    def _get_disk_in_controller(self, controller_type, number, location):
        """
        get the disk assocaited with controller

        Args:
                controller_type (str)    - IDE/SCSI

                number            (int)    - IDE(1:0) 1 is the disk number

                location        (int)    - IDE(1:0) 0 is the location in disk number 1

        Return:
                DiskType    (str)    - diks in location of args(eg: disk in IDE(1:0))

        """
        try:
            _extr_args = "%s,%s,%s" % (controller_type, number, location)
            self._get_vm_info("DiskType", _extr_args)
            return self.DiskType

        except Exception as err:
            self.log.exception("Exception in GetDiskInController")
            raise err

    def _get_disk_path_from_pattern(self, disk_pattern):
        """
        find the disk that matches the disk apttern form disk list

        Args:
                disk_pattern    (str)    - pattern which needs to be matched

        Return:
                eachdisk    (str)        - the disk that matches the pattern
        """
        try:
            _disk_name = os.path.basename(disk_pattern)
            for each_disk in self.DiskList:
                _vm_disk_name = os.path.basename(each_disk)
                if _vm_disk_name == _disk_name:
                    self.log.info("Found the Disk to be filtered in the VM")
                    return each_disk

        except Exception as err:
            self.log.exception("Exception in GetDiskInController")
            raise err

    def migrate_vm(self, vm_name=None):
        """
        Migrate VM to best possible node

        Return:
                NewHost (String) - Hostname the VM migrated to

        Exception:
                An error occurred while checking/creating the registry
        """
        try:
            if vm_name is None:
                vm_name = self.vm_name

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "MigrateVM"
            self.operation_dict["vm_name"] = vm_name
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if "failed" in _stdout:
                self.log.error("The error occurred %s" % _stdout)

        except Exception as err:
            self.log.exception(
                "An error occurred migrating the VM")
            raise err

    def revert_snap(self):
        """
        revert snap of the machine specified
        :return:
            true - if revert snap succeds
            False - on Failure
        """
        try:
            _ps_path = os.path.join(
                self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "RevertSnap"
            self.operation_dict["extra_args"] = "Fresh"
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if '0' in _stdout:
                self.log.info("Snapshot revert was successfull")
                return True
            else:
                return False

        except Exception as err:
            self.log.exception("Exception in revert_snap")
            raise err


class VmwareVM(HypervisorVM):
    """
    Class for VMware VMs
    """
    def __init__(self, Hvobj, vm_name):
        """
        Initialization of vmware vm properties

        _get_vm_host()            - get the host of the VM among the servers list

        _get_vm_info()            - get the particular  information of VM

        _get_disk_list()        - gets the disk list opff the VM

        mount_vmdk()                - Mount the VMDK and return the drive letter

        un_mount_vmdk()            - Unmount the VMDK mounted provided the path

        _get_disk_in_controller()- get the disk in controller attached

        _get_disk_path_from_pattern() - get the list of disk from pattern

        power_off()            - power off the VM

        power_on()            -power on the VM

        delete_vm()            - delete the VM

        update_vm_info()    - updates the VM info
        """
        super(VmwareVM, self).__init__(Hvobj, vm_name)
        self.server_name = Hvobj.server_host_name
        self.vm_props_file = "GetVMwareProps.ps1"
        self.vm_operation_file = "VMwareOperation.ps1"
        self.prop_dict = {
            "server_name": self.server_name,
            "user": self.host_user_name,
            "pwd": self.host_password,
            "vm_name": self.vm_name,
            "extra_args": "$null"
        }

        self.operation_dict = {
            "server_name": self.server_name,
            "user": self.host_user_name,
            "pwd": self.host_password,
            "vm_name": self.vm_name,
            "vm_user": self.user_name,
            "vm_pass": self.password,
            "property": "$null",
            "extra_args": "$null"
        }

        self.GUID = None
        self.IP = None
        self.GuestOS = None
        self.HostName = None
        self._disk_list = None
        self.disk_dict = None
        self.DiskPath = None
        #self.Memory = None
        #self.VMSpace = None
        self.update_vm_info()

    def update_vm_info(self, prop='Basic', os_info=False):
        """
        fetches all the properties of the VM

        Args:
                should have code for two possibilties

                Basic - Basic properties of VM like HostName,
                            especially the properties with which VM can be added as dynamic content

                All   - All the possible properties of the VM

                Set the property VMGuestOS for creating OS Object

        exception:
                if failed to get all the properties of the VM
        """

        try:
            self._get_vm_info(prop)
            if os_info or prop == 'All':
                self.vm_guest_os = self.GuestOS
                self.get_drive_list()

        except Exception as err:
            self.log.exception("Failed to Get  the VM Properties of the VM")
            raise Exception(err)

    def _get_vm_info(self, prop, extra_args="$null"):
        """
        get the basic or all or specific properties of VM

        Args:
                prop         -    basic, All or specific property like Memory

                ExtraArgs    - Extra arguments needed for property listed by ","

        exception:
                if failed to get all the properties of the VM

        """
        try:

            self.log.info(
                "Collecting all the VM properties for VM %s" % self.vm_name)
            _ps_path = os.path.join(self.utils_path, self.vm_props_file)
            self.prop_dict["property"] = prop
            self.prop_dict["extra_args"] = extra_args
            output = self.host_machine._execute_script(_ps_path, self.prop_dict)
            _stdout = output.output

            if _stdout != "":
                stdlines = _stdout.split(';')
                for _each_prop in stdlines:
                    key = _each_prop.split("=")[0]
                    val = _each_prop.split("=")[1]
                    val = val.strip()
                    if val == "":
                        val = None
                    setattr(self, key, val)

        except Exception as err:
            self.log.exception("Failed to Get all the VM Properties of the VM")
            raise Exception(err)

    def mount_vmdk(self, vmdk_name):
        """
        Mount the VMDK provided

        Args:
                vmdk_name            (str)    - vmdk name that has to be mounted

        returns:
                _drive_letter_list    (list)    - List of drive letters that is returned after mount
                                                        [A:,D:]

                                                        False    - if failed to mount
        """
        try:
            _drive_letter_list = []
            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "MountVMDK"
            self.operation_dict["vmdk_name"] = vmdk_name
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if "Success" in _stdout:
                _stdout = _stdout.split("\n")
                for line in _stdout:
                    if "DriveLetter" in line:
                        _drive_letter = line.split("=")[1]
                        _drive_letter = _drive_letter.strip()
                        if "," in _drive_letter:
                            _temp_drive_letter_list = _drive_letter.split(",")
                        else:
                            _temp_drive_letter_list = []
                            _temp_drive_letter_list.append(_drive_letter)
                for each_drive in _temp_drive_letter_list:
                    each_drive = each_drive + ":"
                    _drive_letter_list.append(each_drive)
                for each_drive in _drive_letter_list:
                    self.log.info("drive letter %s" % each_drive)

                return _drive_letter_list
            self.log.error("The error occurred %s" % _stdout)
            return False

        except Exception as exp:
            self.log.exception("Exception in MountVMDK")
            raise Exception("Exception in MountVMDK:" + str(exp))

    def un_mount_vmdk(self, vmdk_name):
        """
        Un-mount the vmdk name provided

        args:
                vmdk_name : vmdk needs to be unmounted

        return:
                True    (bool)         - if vmdk is unmounted

        Exception:
                if fails to un mount

        """

        try:
            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "UnMountVMDK"
            self.operation_dict["vmdk_name"] = vmdk_name
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if "Success" in _stdout:
                return True
            self.log.error("The error occurred %s" % _stdout)
            raise Exception("Exception in UnMountVMDK")

        except Exception as exp:
            self.log.exception("Exception in UnMountVMDK")
            raise Exception("Exception in UnMountVMDK:" + str(exp))

    def power_on(self):
        """
        power on the VM.

        return:
                True - when power on is successful

        Exception:
                When power on failed

        """

        try:

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "PowerOn"
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)

            _stdout = output.output
            if "Success" in _stdout:
                return True
            self.log.error("The error occurred %s" % _stdout)
            raise Exception("Exception in PowerOn")

        except Exception as exp:
            self.log.exception("Exception in PowerOn")
            raise Exception("Exception in PowerOn:" + str(exp))

    def power_off(self):
        """
        power off the VM.

        return:
                True - when power off is successful

        Exception:
                When power off failed

        """

        try:

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "PowerOff"
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)

            _stdout = output.output

            if "Success" in _stdout:
                return True
            else:
                self.log.error("The error occurred %s" % _stdout)
                raise Exception("Exception in PowerOff")

        except Exception as exp:
            self.log.exception("Exception in PowerOff")
            raise Exception("Exception in PowerOff:" + str(exp))

    def delete_vm(self):
        """
        Delete the VM.

        return:
                True - when Delete  is successful
                False -  when delete is failed

        """

        try:

            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["operation"] = "Delete"
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)

            _stdout = output.output
            if "Success" in _stdout:
                return True
            self.log.error("The error occurred {0}".format(_stdout))
            return False

        except Exception as exp:
            self.log.exception("Exception in DeleteVM {0}".format(exp))
            return False

    def _get_disk_in_controller(self, controller_type, number, location):
        """
        get the disk associated with controller

        Args:
                controller_type (str)    - IDE/SCSI

                number            (int)    - IDE(1:0) 1 is the disk number

                location        (int)    - IDE(1:0) 0 is the location in disk number 1

        Return:
                DiskType    (str)    - disks in location of args(eg: disk in IDE(1:0))

        """
        try:
            _extr_args = "%s,%s,%s" % (controller_type, number, location)
            self._get_vm_info("DiskType", _extr_args)
            return self.DiskType

        except Exception as exp:
            self.log.exception("Exception in _get_disk_in_controller")
            raise exp

    def _get_disk_path_from_pattern(self, disk_pattern):
        """
        find the disk that matches the disk apttern form disk list

        Args:
                disk_pattern    (str)    - pattern which needs to be matched

        Return:
                each_disk    (str)        - the disk that matches the pattern
        """
        try:
            _disk_name = os.path.basename(disk_pattern)
            for each_disk in self.DiskList:
                _vm_disk_name = os.path.basename(each_disk)
                if _vm_disk_name == _disk_name:
                    self.log.info("Found the Disk to be filtered in the VM")
                    return each_disk

        except Exception as exp:
            self.log.exception("Exception in _get_disk_path_from_pattern")
            raise exp

    def live_browse_vm_exists(self, _vm, vsa_restore_job):
        """
        Check the VM mounted during live browse is present or not
        Args:
            _vm (str)   :       Name of the vm which is mounted
            vsa_backup_job (int)    :       File level restore job

        Returns:
            True    :       If the VM exists
            False   :       If the VM doesn't esists
        """
        try:
            vmname = _vm + "_" + str(vsa_restore_job) + "_GX_BACKUP"
            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["vm_name"] = vmname
            self.operation_dict["property"] = "VMExists"
            output = self.host_machine._execute_script(_ps_path, self.operation_dict)
            _stdout = output.output
            if "True" in _stdout:
                return True
            else:
                return False

        except Exception as err:
            self.log.exception(
                "Exception while vm existence check " + str(err))
            raise err

    def live_browse_ds_exists(self, _dslist):
        """
        Check the VM mounted during live browse is present or not
        Args:
            _dslist (list)   :       List of DS which is mounted

        Returns:
            True    :       If the DS exists
            False   :       If the DS doesn't esists
        """
        try:
            _ps_path = os.path.join(self.utils_path, self.vm_operation_file)
            self.operation_dict["property"] = "DSExists"
            _failures = 0
            for _ds in _dslist:
                self.operation_dict["vm_name"] = _ds
                output = self.host_machine._execute_script(_ps_path, self.operation_dict)
                _stdout = output.output
                if _stdout != "False":
                    _failures += 1
            if _failures != 0:
                return True
            else:
                return False

        except Exception as err:
            self.log.exception(
                "Exception while DS existence check " + str(err))
            raise err

    @property
    def disk_list(self):
        """to fetch the disk in the VM
        Return:
            disk_list   (list)- list of disk in VM
            e.g:[ide0-0-test1.vhdx]
        """
        self.disk_dict = self._get_disk_list
        if self.disk_dict:
            self._disk_list = self.disk_dict.keys()

        else:
            self._disk_list = []

        return self._disk_list

    @property
    def _get_disk_list(self):
        """
        get the list of disk in the VM

        Returns:
                _disk_dict : with keys as disk name and value as snapshot associated with diskname

                _diks_dict = {
                        "test1.vhdx":["test1_184BDFE9-1DF5-4097-8BC3-06128C581C42.avhdx",
                        "test1_184BDEF9-1DF5-4097-8BC3-06128C581c82.avhdx"]
                }

        """
        try:
            _disk_dict = {}
            if self.DiskPath is None:
                self._get_vm_info('DiskPath')

            if self.DiskPath is not None:
                if "," in self.DiskPath:
                    temp_list = self.DiskPath.split(",")

                else:
                    temp_list = [self.DiskPath]

                for each_disk_list in temp_list:
                    final_disk = (each_disk_list.split("::")[0]).strip()
                    _temp_disk_list = (each_disk_list.split("::")[1]).strip()
                    if " " in _temp_disk_list:
                        _disk_list = _temp_disk_list.split(" ")
                    else:
                        _disk_list = [_temp_disk_list]

                    _disk_dict[final_disk] = _disk_list

            else:
                self.log.info("Cannot collect Disk  Path information")

            return _disk_dict
        except Exception as err:
            self.log.exception("Failed to Get all the VM Properties of the VM")
            raise Exception(err)


class AzureVM(HypervisorVM):
    """
    This is the main file for all AzureRM VM operations
    """

    def __init__(self, Hvobj, vm_name):
        """
        Initialization of AzureRM VM properties

        get_drive_list()          -  get the drive list for the VM

        _get_vm_info()            -  get the information about the particular VM

        get_vm_guid()             -  gets the GUID of Azure VM

        get_nic_info()            -  get all network attached to that VM

        get_VM_size()             -  gets the size of the Azure VM

        get_cores()               -  get the cores of the VM

        get_Disk_info()           -  get all the disk info of VM

        wait_for_vmoperation_to_complete() - waiting for some specified operation to complete

        power_off()            - power off the VM

        power_on()             - power on the VM

        delete_vm()            - delete the VM

        get_status_of_vm()     - get the status of VM like started.stopped

        get_OS_type()          - update the OS type of the VM

        get_subnet_ID()        - Update the subnet_ID for VM

        get_IP_address()       - gets the IP address of the VM

        update_vm_info()       - updates the VM info

        """
        import requests
        super(AzureVM, self).__init__(Hvobj, vm_name)
        self.azure_baseURL = 'https://management.azure.com'
        self.azure_apiversion = "api-version="
        self.subscriptionID = self.Hvobj.subscriptionID
        self.appID = self.Hvobj.appID
        self.tenantID = self.Hvobj.tenantID
        self.app_password = self.Hvobj.app_password
        self.azure_session = requests.Session()
        self.vm_name = vm_name
        self.access_token = self.Hvobj.access_token
        self.storageaccount_type = None
        self.resource_group_name = self.Hvobj.get_resourcegroup_name(self.vm_name)
        self.vm_files_path = self.resource_group_name
        self.network_name = None
        self.subnetId = None
        self._vm_info = {}
        self.disk_info = {}
        self.disk_dict = {}
        self.nic = []
        self._disk_list = None
        self._get_vm_info()
        self.update_vm_info()


    @property
    def azure_vmurl(self):
        if self.resource_group_name is None:
            self.Hvobj.get_resourcegroup_name(self.vm_name)

        azure_vmurl = "https://management.azure.com/subscriptions/%s/resourceGroups" \
                      "/%s/providers/Microsoft.Compute/virtualMachines" \
                      "/%s"%(self.subscriptionID, self.resource_group_name, self.vm_name)
        return azure_vmurl

    @property
    def vm_info(self):
        if self._vm_info[self.vm_name] == {}:
            self.get_vm_info()
        return self._vm_info[self.vm_name]

    @vm_info.setter
    def vm_info(self, value):
        self._vm_info[self.vm_name] = value

    @property
    def access_token(self):
        self.Hvobj.check_for_access_token_expiration()
        return self.Hvobj.access_token

    access_token.setter
    def access_token(self, token):
        self.Hvobj._access_token = token

    @property
    def default_headers(self):
        self.log.info("Getting the headers")
        self.Hvobj._default_headers = {"Content-Type":"application/json",
                                       "Authorization":"Bearer %s"%self.access_token}
        return self.Hvobj._default_headers

    @property
    def drive_list(self):
        if self._drive_list is None:
            self.get_drive_list()
        return self._drive_list

    @property
    def disk_list(self):
        """to fetch the disk in the VM
        Return:
            disk_list   (list)- list of disk in VM

        """
        if self.disk_dict:
            self._disk_list = self.disk_dict.keys()

        else:
            self._disk_list = []

        return self._disk_list

    def get_drive_list(self):

        """
        Returns the drive list for the VM
        """
        try:
            _temp_drive_letter = {}
            storage_details = self.machine.get_storage_details()

            if self.GuestOS == "Windows":
                _drive_regex = "^[a-zA-Z]$"
                for _drive, _size in storage_details.items():
                    if re.match(_drive_regex, _drive):
                        _drive = _drive + ":"
                        _temp_drive_letter[_drive.split(":")[0]] = _drive
                del self._drive_list['D']

            else:
                index = 1
                for _drive, _volume in storage_details.items():
                    if "/dev/sd" in _drive:
                        _temp_drive_letter["MountDir-" + str(index)] = _volume["mountpoint"]
                        index = index + 1

                    if "dev/mapper" in _drive:
                        _volume_name = _drive.split("/")[-1]
                        _temp_drive_letter[_volume_name] = _volume["mountpoint"]

            self._drive_list = _temp_drive_letter
            if not self._drive_list:
                raise Exception("Failed to Get Volume Details for the VM")

        except Exception as err:
            self.log.exception(
                "An Exception Occurred in Getting the Volume Info for the VM {0}".format(err))
            return False

    def _get_vm_info(self):
        """
        Get all VM Info related to the given VM.
        """
        try:

            self.log.info("VM information :: Getting all information of VM [%s]"%(self.vm_name))
            vm_infourl = self.azure_vmurl+"?api-version=2017-12-01"
            response = self.azure_session.get(vm_infourl, headers=self.default_headers)
            self.log.info("Dump vm_infourl: "+ vm_infourl)
            data = response.json()
            if response.status_code == 200:
                self.vm_info = data
                self.log.info("vm_info %s of VM %s is successfully obtained "%(data, self.vm_name))

            elif response.status_code == 404:
                self.log.info("There was No VM in Name %s , please check the VM name"%self.vm_name)
                self.vm_info = False
                 # No VMs found

            else:
                raise Exception("VM  data cannot be collected")

        except Exception as err:
            self.log.exception("Exception in get_vm_info")
            raise Exception(err)


    def get_vm_guid(self):
        """
        Gets the GUID of Azure VM
        """
        try:
            self.log.info("Getting the size information for VM %s"%self.vm_name)
            data = self.vm_info
            self.log.info("VM  details of the VM is %s"%data)
            self.guid = data["properties"]["vmId"]

        except Exception as err:
            self.log.exception("Exception in get_vm_guid")
            raise Exception(err)

    def get_nic_info(self):
        """
        Get all network attached to that VM
        """
        try:

            self.log.info("Getting the network cards infor for VM %s"%self.vm_name)
            data = self.vm_info
            nic_names_id = data["properties"]["networkProfile"]["networkInterfaces"]
            for eachName  in nic_names_id:
                    nic_name = eachName["id"].split("/")[-1]
                    self.nic.append(nic_name)


        except Exception as err:
            self.log.exception("Exception in get_nic_info")
            raise Exception(err)

    def get_VM_size(self):
        """
        Get the VMSize
        """
        try:

            self.log.info("Getting the size information for VM %s"%self.vm_name)
            data = self.vm_info
            self.log.info("VM  details of the VM is %s"%data)
            self.vm_size = data["properties"]["hardwareProfile"]["vmSize"]

        except Exception as err:
            self.log.exception("Exception in get_vm_size")
            raise Exception(err)

    def get_cores(self):
        """
        Get the cores of the VM
        """
        try:
            if not self.vm_size is None:
                self.log.info("VM information ::  Getting memory  information of VM [%s]"%(self.vm_name))
                vm_sizeurl = self.azure_vmurl+"/vmSizes?api-version=2017-12-01"
                response = self.azure_session.get(vm_sizeurl, headers=self.default_headers)
                self.log.info("Dump Azure Size URL: "+ vm_sizeurl)
                data = response.json()
                if response.status_code == 200:
                    for eachsize in data["value"]:
                        if eachsize["name"] == self.vm_size:
                            self.NoofCPU = eachsize["numberOfCores"]
                            _memory = ((eachsize["memoryInMB"])/1024)
                            self.memory = _memory

                elif response.status_code == 404:
                    self.log.info("There was No VM in Name %s ,check the VM name"%self.vm_name)
                    self.size_info = False
                     # No VMs found

                else:
                    raise Exception("VM  data cannot be collected")

        except Exception as err:
            self.log.exception("Exception in get_vm_size")
            raise Exception(err)


    def get_Disk_info(self):
        """
        Get all the disk info of VM
        """
        try:

            self.log.info("Getting the os disk and data disk information for VM %s"%self.vm_name)
            data = self.vm_info
            os_disk_details = data["properties"]["storageProfile"]["osDisk"]
            self.log.info("os disk detaisl of the VM is %s"%os_disk_details)
            if 'managedDisk' in os_disk_details:
                self.disk_info["OsDisk"] = os_disk_details["managedDisk"]["id"]
                self.storageaccount_type = os_disk_details["managedDisk"]["storageAccountType"]
                data_disk_details = data["properties"]["storageProfile"]["dataDisks"]
                for each in data_disk_details:
                    self.disk_info[each["name"]] = each["managedDisk"]["id"]
            else:
                self.disk_info["OsDisk"] = os_disk_details["vhd"]["uri"]
                data_disk_details = data["properties"]["storageProfile"]["dataDisks"]
                for each in data_disk_details:
                     self.disk_info[each["name"]] = each["vhd"]["uri"]

            self.disk_dict = self.disk_info
            self.Diskcount = len(self.disk_info.keys())

        except Exception as err:
            self.log.exception("Exception in get_disk_info")
            raise Exception(err)

    def wait_for_vmoperation_to_complete(self, operation_status):
        """
        waiting for some specified operation to complete
        """
        try:
            is_complete = False
            ret_code = True
            count = 0
            while (not is_complete) and (count < 3):
                if self.get_status_of_vm():
                    if self.vm_status == operation_status:
                        is_complete = True
                        ret_code = True

                    else:
                        self.log.info("VM was not %s ,waiting for some more time" %operation_status)
                        time.sleep(60)
                        count = count+1
                        ret_code = False

                else:
                    self.log.info("Couldn't find if task is completed, Failure reason:"%(data.reason))
                    is_complete = True
                    ret_code = False
            return ret_code

        except Exception as err:
            self.log.exception("Exception in wait for completion")
            raise Exception(err)

    def power_on(self):
        """
        Power on the Azure VM
        """
        try:
            body = {}
            self.log.info("vm operation ::  power on VM [%s]"%(self.vm_name))
            vmurl = self.azure_vmurl+"start?api-version=2017-12-01"
            data = self.azure_session.post(vmurl, headers=self.default_headers)
            if data.status_code == 200:
                ret_code = True

            elif data.status_code == 202:
                ret_code = self.wait_for_vmoperation_to_complete("Ready")

            elif data.status_code == 401:
                self.log.info("got the unauthorised error, please check the credentials and token ")
                raise Exception("unauthorised error")
            else:
                raise Exception("Failed to Power on the VM")

            return ret_code

        except Exception as err:
            self.log.exception("Exception in PowerOn")
            raise Exception(err)

    def power_off(self):
        """
        Power off the VM
        """
        try:
            body = {}
            self.log.info("vm operation ::  power off vm [%s]"%(self.vm_name))
            vmurl = self.azure_vmurl+"/powerOff?api-version=2017-12-01"
            data = self.azure_session.post(vmurl, header=self.default_headers)
            response = eval(data)
            if data.status_code == 200:
                ret_code = True
            elif data.status_code == 202:
                ret_code = self.wait_for_vmoperation_to_complete("Ready")

            elif data.status_code == 401:
                self.log.info("Got the unauthorised error, please check the credentials and token ")
                raise Exception("unAuthorised error")

            else:
                raise Exception("Failed to Power off the VM")

            return ret_code

        except Exception as err:
            self.log.exception("Exception in Poweroff")
            raise Exception(err)


    def get_status_of_vm(self):
        """
        get the status of VM like started.stopped
        """
        try:
            body = {}
            self.log.info("VM Operation ::  Get the Status of VM [%s]"%(self.vm_name))
            vmurl = self.azure_vmurl+"/InstanceView?api-version=2017-12-01"
            self.log.info("Getting status of the VM URL is %s"%vmurl)
            data = self.azure_session.get(vmurl, headers=self.default_headers)
            if data.status_code == 200:
                status_data = data.json()
                if "vmAgent" in status_data.keys():
                    self.vm_state = status_data["vmAgent"]["statuses"][0]["displayStatus"]

            elif data.status_code == 404:
                self.log.info("VM Not found")


            else:
                raise Exception("Cannot get the status of VM")

        except Exception as err:
            self.log.exception("Exception in getStatusofVM")
            raise Exception(err)

    def delete_vm(self):
        """
        Delete VM in Azure
        """
        try:
            body = {}
            count = 0
            self.log.info("VM Operation ::  Delete  VM [%s]"%(self.vm_name))
            vmurl = self.azure_vmurl+"?api-version=2017-12-01"
            data = self.azure_session.delete(vmurl, headers=self.default_headers)
            if data.status_code == 200:
                ret_code = True
            elif data.status_code == 202:
                self.log.info("the Operation has triggered, need to wait for Vm to delete")
                while((self.get_status_of_vm != None) and (count < 3)):
                    self.log.info("VM deletion operation is not completeed , sleeping for 60 secs")
                    count = count+1
                    time.sleep(60)

            elif data.status_code == 401:
                self.log.info("Got the unauthorised error, please check the credentials and token ")
                raise Exception("unAuthorized error")
            else:
                raise Exception("Cannot delete the VM")

            #just issing public ip delete requests too as it costs
            if not self.public_IPurl is None:
                data = self.azure_session.delete(self.public_IPurl, headers=self.default_headers)

        except Exception as err:
            self.log.exception("Exception in DeleteVM")
            raise Exception(err)

    def get_OS_type(self):
        """
        Update the OS Type
        """

        try:
            self.log.info("Getting the os disk and data disk  info for VM %s"%self.vm_name)
            data = self.vm_info
            guest_os = data['properties']["storageProfile"]["osDisk"]["osType"]
            self.log.info("os disk detaisl of the VM is %s"%guest_os)
            setattr(self, "GuestOS", guest_os)
            self.log.info("OS type is : %s"%self.GuestOS)

        except Exception as err:
            self.log.exception("Exception in GetOSType")
            raise Exception(err)

    def get_subnet_ID(self):
        """
        Update the subnet_ID for VM
        """

        try:
            self.log.info("subnet info for VM %s and NetworkInterface %s"%(self.vm_name, self.network_name))
            azure_list_nwurl = self.azure_baseURL+"/subscriptions/"+self.subscriptionID\
                               +"/providers/Microsoft.Network/networkInterfaces?api-version=2018-01-01"
            self.log.info("Trying to get list of VMs usign post %s"%azure_list_nwurl)
            data = self.azure_session.get(azure_list_nwurl, headers=self.default_headers)
            if data.status_code == 200:
                _all_nw_data = data.json()
                for each_nw in _all_nw_data["value"]:
                    if each_nw["name"] == self.network_name:
                        ip_config_info = each_nw["properties"]["ipConfigurations"]
                        for each_ip_info in ip_config_info:
                            self.subnetId = each_ip_info["properties"]["subnet"]["id"]
                            break
            else:
                raise Exception("Failed to get network details for the VM")


        except Exception as err:
            self.log.exception("Exception in GetSubnetID")
            raise Exception(err)

    def get_IP_address(self):
        """
        Get the Ip address of the VM
        """
        try:
            self.log.info("Get restored VM IP details")
            data = self.vm_info
            self.log.info("VM deets : %s"%data)

            nw_interfaces = data['properties']["networkProfile"]["networkInterfaces"]
            for each_network in nw_interfaces:
                    nw_interface_value = each_network["id"]

            nw_interface_url = self.azure_baseURL+nw_interface_value+"?api-version=2018-01-01"
            self.log.info(" URL level 1 is %s"%nw_interface_url)

            response = self.azure_session.get(nw_interface_url, headers=self.default_headers)
            nic_interface_info = response.json()
            self.log.info("Level 2 for network interfaces is : %s"%nic_interface_info)

            ip_config_info = nic_interface_info["properties"]["ipConfigurations"]
            for each_ip_info in ip_config_info:
                    vm_vnet_props = each_ip_info["properties"]
                    break

            if "publicIPAddress" in vm_vnet_props:
                ip_config_info_value = vm_vnet_props["publicIPAddress"]["id"]
                self.log.info(ip_config_info_value)
                self.public_IPurl = self.azure_baseURL+ip_config_info_value+"?api-version=2018-01-01"
                self.log.info("URL : %s"%self.public_IPurl)
                response = self.azure_session.get(self.public_IPurl, headers=self.default_headers)
                ip_info_value = response.json()
                self.log.info("Public IP details : %s"%ip_info_value)
                if response.status_code == 200:
                    vm_ip = ip_info_value["properties"]["ipAddress"]
                    setattr(self, "IP", vm_ip)

            else:
                vm_ip = vm_vnet_props["privateIPAddress"]
                setattr(self, "IP", vm_ip)

            self.subnetId = vm_vnet_props["subnet"]["id"]
            nw_name = nic_interface_info["id"]
            self.network_name = nw_name.split("/")[-1]

            setattr(self, "HostName", vm_ip)

        except Exception as err:
            self.log.exception("Exception in get_vm_ip_address")
            raise Exception(err)

    def update_vm_info(self, prop='Basic', os_info=False):
        """
         fetches all the properties of the VM

         Args:
                 should have code for two possibilties

                 Basic - Basic properties of VM like cores,GUID,disk

                 All   - All the possible properties of the VM

                 Set the property VMGuestOS for creating OS Object

                 fetches some particular specified property

         exception:
                 if failed to get all the properties of the VM
         """
        try:
            if self.vm_info:
                self.get_vm_guid()
                self.get_VM_size()
                self.get_cores()
                self.get_Disk_info()
                self.get_status_of_vm()
                if prop == 'All':
                    self.get_IP_address()
                    self.get_nic_info()
                    self.get_subnet_ID()
                    self.get_OS_type()
                    self.vm_guest_os = self.GuestOS
                    self.get_drive_list()
                elif hasattr(self, prop):
                    return getattr(self, prop, None)

            else:
                self.log.info("VM info was not collected for this VM")


        except Exception as err:
            self.log.exception("Failed to Get  the VM Properties of the VM")
            raise Exception(err)


class FusionComputeVM(HypervisorVM):
    """
    Class for Fusion Compute  VMs
    """

    def __init__(self, hvobj, vm_name):
        """
         Initialization of vmware vm properties
        :param hvobj:       (obj) Hypervisor class object for Fusion Compute
        :param vm_name:     (str) name of the VM for which properties can be fetched
        """

        super(FusionComputeVM, self).__init__(hvobj, vm_name)
        self.server_name = hvobj.server_host_name
        self.hvobj = hvobj
        self.vm_url = 'http://{0}:7070{1}'.format(self.server_name, self.hvobj.vm_dict[vm_name])
        self._vm_operation_services_dict = FusionComputeServices.get_vm_operation_services(self.server_name,
                                                                                           self.hvobj.vm_dict[vm_name])
        self.GUID = None
        self.IP = None
        self.GuestOS = None
        self.HostName = None
        self._disk_list = None
        self.DiskPath = None
        self.update_vm_info()

    def update_vm_info(self, prop='Basic', os_info=False):
        """
        fetches all the properties of the VM

        Args:
                should have code for two possibilties

                Basic - Basic properties of VM like HostName,
                            especially the properties with which VM can be added as dynamic content

                All   - All the possible properties of the VM

                Set the property VMGuestOS for creating OS Object

        exception:
                if failed to get all the properties of the VM
        """

        try:
            self._get_vm_info(prop)
            if prop == 'All':
                self.vm_guest_os = self.GuestOS
                self.get_drive_list()

            elif hasattr(self, prop):
                return getattr(self, prop, None)

        except Exception as err:
            self.log.exception("Failed to Get  the VM Properties of the VM with the exception {0}".format(err))
            raise Exception(err)

    def _get_vm_info(self, prop, extra_args=None):
        """
        get the basic or all or specific properties of VM

        Args:
                prop         -    basic, All or specific property like Memory

                ExtraArgs    - Extra arguments needed for property listed by ","

        exception:
                if failed to get all the properties of the VM

        """
        try:
            self.log.info(
                "Collecting all the VM properties for VM %s" % self.vm_name)

            flag, response = self.hvobj._make_request('GET', self.vm_url)
            if flag:
                response_json = response.json()
                self.GUID = response_json['uuid']
                self.IP = response_json['vmConfig']['nics'][0]['ip']
                self.GuestOS = response_json['osOptions']['osType']
                self.HostName = response_json['osOptions']['hostname']
                self.nic_count = len(response_json['vmConfig']['nics'])
                self.disks = response_json['vmConfig']['disks']
                self.disk_list = [disk['datastoreUrn'] for disk in self.disks]
                self.Diskcount = len(self.disks)
                self.NoofCPU = response_json['vmConfig']['cpu']['quantity']
                self.Memory = (response_json['vmConfig']['memory']['quantityMB'])/1024
                self.VMSpace = self._get_disk_size(response_json)
                return

            raise Exception("failed with error {0}".format(response.json()))

        except Exception as err:
            self.log.exception(
                    "Failed to Get  the VM Properties of the VM with the exception {0}".format(err)
                    )
            raise Exception(err)

    def _get_disk_size(self, response):
        """
        get teh total used space of the VM
        :param
            response: response object of VMs API
        :return:
        disk_space  (int)   : total space occupied by VM in GB
        """

        try:
            _disk_list = response['vmConfig']['disks']
            disk_space = 0
            for disk in _disk_list:
                disk_space += disk['quantityGB']

            return disk_space

        except Exception as err:
            self.log.exception(
                "Failed to Get  the VM disk space of the VM with the exception {0}".format(err))
            raise Exception(err)

    def power_on(self):
        """
        power on the VM.

        return:
                True - when power on is successful

        Exception:
                When power on failed

        """

        try:

            flag, response = self.hvobj._make_request('GET', 
                                                      self._vm_operation_services_dict['START_VM'])
            if flag:
                return True

            self.log.error("Error occurred while powering on VM {0}".format(response.json()))

        except Exception as exp:
            self.log.exception("Exception in PowerOn{0}".format(exp))
            return False

    def power_off(self):
        """
        power off the VM.

        return:
                True - when power off is successful

        Exception:
                When power off failed

        """

        try:

            flag, response = self.hvobj._make_request('GET', 
                                                      self._vm_operation_services_dict['STOP_VM'])
            if flag:
                return True

            self.log.error("Error occurred while powering on VM {0}".format(response.json()))

        except Exception as exp:
            self.log.exception("Exception in PowerOff{0}".format(exp))
            return False

    def delete_vm(self):
        """
        Delete the VM.

        return:
                True - when Delete  is successful
                False -  when delete is failed

        """

        try:

            flag, response = self.hvobj._make_request('GET', self.vm_url)
            if flag:
                return True

            self.log.error("Error occurred while powering on VM {0}".format(response.json()))

        except Exception as exp:
            self.log.exception("Exception in Deleting the VM {0}".format(exp))
            return False

    def restart_vm(self):
        """
        restart the VM.

        return:
                True - when restart  is successful
                False -  when restart is failed

        """

        try:

            flag, response = self.hvobj._make_request('GET', 
                                                      self._vm_operation_services_dict['RESTART_VM'])
            if flag:
                return True

            self.log.error("Error occurred while restarting on VM {0}".format(response.json()))

        except Exception as exp:
            self.log.exception("Exception in restarting the VM {0}".format(exp))
            return False

class OracleVMHelper(HypervisorVM):
    """
    This is the main file for all Oracle VM operations
    """

    def __init__(self, hvobj, vm_name):
        """
        Initialization of Oracle VM properties

        _get_disk_info()            - Get the name, path and size of the disks available

        _get_nic_info()             - Get the name, IP and MACs of the available NICs

        _get_vm_info()              - Fetches Basic/Advanced VM properties

        update_vm_info()            - Fetch all the properties of vm by calling _get_vm_info()

        _wait_for_job()             - Waits on a job to complete and returns the result

        _do_vm_operation()          - Perform a VM operation requested

        power_off()                 - power off the VM

        power_on()                  - power on the VM

        delete_vm()                 - delete the VM

        """

        super(OracleVMHelper, self).__init__(hvobj, vm_name)
        self.hvobj = hvobj
        self.server_name = "oravmserver.commvault.com"
        self._server_host_name = self.hvobj.server_host_name
        self.vm_name = vm_name
        self._vm_id = self.hvobj.vm_dict[vm_name].split("/")[-1]
        self._base_url = "https://"+self._server_host_name+":7002/ovm/core/wsapi/rest"

        self.GUID = None
        self.IP = None
        self.GuestOS = None
        self.HostName = None
        self.disk_path = None
        self.Memory = None
        self.disk_list = None
        self._vm_state = None
        self.cpu_count = None
        self.update_vm_info()

    def _get_disk_info(self, vm_disk_mapping_list):
        """
        Get the name, path and size of the disks available
        Args:
            vm_disk_mapping_list:  response of the disk mapping call

        Returns: (list)     List of the disk with Name, Path and Size

        """

        _disks = []
        try:
            for disk in vm_disk_mapping_list:
                flag, disk_mapping_info = self.hvobj._make_request("GET", disk["uri"])
                disk_mapping_info = disk_mapping_info.json()
                flag, virtual_disk = self.hvobj._make_request("GET", disk_mapping_info["virtualDiskId"]["uri"])
                virtual_disk = virtual_disk.json()
                _vm_disk = {}
                _vm_disk["name"] = virtual_disk.get("name", disk_mapping_info["virtualDiskId"]["name"])
                _vm_disk["path"] = virtual_disk.get("path", "")
                _vm_disk["size"] = VirtualServerUtils.bytesto(virtual_disk["size"], "GB")
                _disks.append(_vm_disk)
            return _disks
        except Exception as err:
            self.log.exception("An exception occurred in _get_disk_info")
            raise Exception(err)

    def _get_nic_info(self, nics_list):
        """
        Get the name, IP and MACs of the available NICs
        Args:
            nics_list: list if the nics

        Returns: (list)     list of dicts with name, ip and mac address

        """

        _nics = []
        try:
            for nic in nics_list:
                flag, nic_response = self.hvobj._make_request("GET", nic["uri"])
                nic_response = nic_response.json()
                _vm_nic = {}
                _vm_nic["name"] = nic_response["name"]
                _vm_nic["macAddress"] = nic_response["macAddress"]
                _vm_nic["ipAddress"] = []
                if len(nic_response["ipAddresses"]) > 0:
                    _ip_addresses = []
                    for ip_address in nic_response["ipAddresses"]:
                        _ip_addresses.append(ip_address["address"])
                    _vm_nic["ipAddress"] = _ip_addresses

                _nics.append(_vm_nic)
            return _nics
        except Exception as err:
            self.log.exception("An exception occurred in _get_nic_info")
            raise Exception(err)

    def _get_vm_info(self, prop):
        """
        Fetches Basic/Advanced VM properties
        Args:
            prop: level of properties that needs to be fetched

        Returns:Sets the VM properties to instance and returns the
                 vm rest call json

        """

        _vm_url = self._base_url+"/Vm/"+self._vm_id

        try:
            self._vm_info = {}
            flag, vm_response = self.hvobj._make_request("GET", _vm_url)
            if flag:
                self._vm_info = vm_response.json()
                self._vm_state = self._vm_info["vmRunState"]
                self.GuestOS = VirtualServerUtils.get_os_flavor(self._vm_info["osType"])
                self.cpu_count = self._vm_info["cpuCount"]
                self.Memory = VirtualServerUtils.bytesto(self._vm_info["memory"] * (1024 ** 2), "GB")
                self.disks = self._get_disk_info(self._vm_info["vmDiskMappingIds"])
                self.disk_list = [disk["name"] for disk in self.disks]
                self.disks_count = len(self.disks)
                self.nics = self._get_nic_info(self._vm_info["virtualNicIds"])
                self.IP = self.nics[0]["ipAddress"][0] if \
                    len(self.nics[0]["ipAddress"]) else self.IP
                self.nics_count = len(self.nics)
                self.VMSpace = sum(disk["size"] for disk in self.disks)
            return self._vm_info
        except Exception as err:
            self.log.exception("An exception occurred while making a call to {}".format(_vm_url))
            raise Exception(err)

    def update_vm_info(self, prop='Basic', os_info=False):
        """
        fetches all the properties of the VM

        Args:
                should have code for two possibilties

                Basic - Basic properties of VM like HostName,
                            especially the properties with which VM can be added as dynamic content

                All   - All the possible properties of the VM

                Set the property VMGuestOS for creating OS Object

        exception:
                if failed to get all the properties of the VM
        """

        try:
            self._get_vm_info(prop)
            self.vm_guest_os = self.GuestOS
            if prop == 'All':
                self.get_drive_list()

            elif hasattr(self, prop):
                return getattr(self, prop, None)

        except Exception as err:
            self.log.exception(
                    "Failed to Get  the VM Properties of the VM with the exception {0}".format(err)
                    )
            raise Exception(err)

    def _wait_for_job(self, job_uri, update_vm_properties=False, pooling_interval=10):
        """
        Waits on a job to complete and returns the result
        Args:
            job_uri: uri for making the job request
            update_vm_properties: when set to True will update the VM properties
                                     after the job is completed
            pooling_interval: job pooling time

        Returns: (boolean)  Job Result

        """

        while True:
            sleep(pooling_interval)
            job_request_flag, job_response = self.hvobj._make_request("GET", job_uri)
            job = job_response.json()
            if job['summaryDone']:
                self.log.info
                ('{name}: {runState}'.format(name=job['name'], runState=job['jobRunState']))
                if job['jobRunState'].upper() == 'FAILURE':
                    raise Exception('Job failed: {error}'.format(error=job['error']))
                elif job['jobRunState'].upper() == 'SUCCESS':
                    if update_vm_properties:
                        self.update_vm_info()
                    return job['done']
                    break
                else:
                    break

    def _do_vm_operation(self, operation_type=None, vm_id=None, method="PUT", operation_url=None):
        """
        Perform a VM operation requested
        Args:
            operation_type: type of operation - start, stop, restart
            vm_id: id of the VM operation should performed on
            method: REST methods
            operation_url: overwrites operation_type when provided

        Returns:

        """
        if operation_url is not None:
            _vm_operation_url = operation_url
        else:
            _vm_operation_url = "/".join([self._base_url, 'Vm', self._vm_id, operation_type])
        request_flag, operation_response = self.hvobj._make_request(method, _vm_operation_url)
        operation_response = operation_response.json()
        return self._wait_for_job(operation_response["id"]["uri"])

    def power_on(self):
        """
        Power On the VM.

        return:
                True - when action  is successful
                False -  when action is failed

        """
        job_result = False
        if self._vm_state.upper() != "RUNNING":
            job_result = self._do_vm_operation("start", self._vm_id)
        return job_result

    def power_off(self):
        """
        Power off the VM.

        return:
                True - when action  is successful
                False -  when action is failed

        """
        job_result = False
        if self._vm_state.upper != "STOPPED":
            """
            If power on operation ran recently this task will take more than a minute
            """
            job_result = self._do_vm_operation("stop", self._vm_id)
        return job_result

    def delete_vm(self):
        """
        Delete the VM.

        return:
                True - when action  is successful
                False -  when action is failed

        """
        job_result = False
        if self._vm_state == "STOPPED":
            _delete_url = "/".join([self._base_url, 'Vm', self._vm_id])
            job_result = self._do_vm_operation(method="DELETE", operation_url=_delete_url)
            return job_result
        else:
            if self.power_off():
                self.delete_vm()

    def restart_vm(self):
        """
        Restart the VM.

        return:
                True - when action  is successful
                False -  when action is failed

        """
        if self._vm_state.upper() == "RUNNING":
            """
            If power on operation ran recently this task will take more than a minute
            """
            return self._do_vm_operation("restart", self._vm_id)
        else:
            self.log.error("To restart, VM should be in running state. Current state is {}".format(self._vm_state))
