# -*- coding: utf-8 -*-

# --------------------------------------------------------------------------
# Copyright © Commvault Systems, Inc.
# See LICENSE.txt in the project root for
# license information.
# --------------------------------------------------------------------------

"""Helper file to manage security associations on this commcell

SecurityAssociation is the only class defined in this file

SecurityAssociation:
    __init__()                  --  initializes security class object

    __str__()                   --  returns all the users associated with the commcell

    __repr__()                  --  returns the string for the instance of the User class

    _get_security_roles()       --  gets the list of all the security roles applicable
                                        on this commcell

    _add_security_association() --  adds the security association with client or clientgroup

    has_role()                  --  checks if specified role exists on commcell

"""

from past.builtins import basestring

from ..exception import SDKException


class SecurityAssociation(object):
    """Class for managing the security associations roles on the commcell"""

    def __init__(self, commcell_object, class_object):
        """Initializes the security associations object

            Args:
                commcell_object     (object)     --     instance of the Commcell class

                class_object         (object)     --    instance of the class on which we want to
                                                            manage security operations
        """
        self._commcell_object = commcell_object

        from ..client import Client
        if isinstance(class_object, Client):
            self._entity_list = {
                "entity": [{
                    "clientId": int(class_object.client_id),
                    "_type_": 3
                }]
            }

        self._roles = self._get_security_roles()

    def __str__(self):
        """Representation string consisting of all available security roles on this commcell.

            Returns:
                str - string of all the available security roles on this commcell
        """
        representation_string = '{:^5}\t{:^20}\n\n'.format('S. No.', 'Roles')

        for index, role in enumerate(self._roles):
            sub_str = '{:^5}\t{:20}\n'.format(index + 1, role)
            representation_string += sub_str

        return representation_string.strip()

    def __repr__(self):
        """Representation string for the instance of the Security class."""
        return "Security class instance for Commcell: '{0}'".format(
            self._commcell_object.commserv_name
        )

    def _get_security_roles(self):
        """Returns the list of available roles on this commcell"""
        GET_SECURITY_ROLES = self._commcell_object._services['GET_SECURITY_ROLES']

        flag, response = self._commcell_object._cvpysdk_object.make_request(
            'GET', GET_SECURITY_ROLES
        )

        if flag:
            if response.json() and 'roleProperties' in response.json():
                role_props = response.json()['roleProperties']

                roles = {}

                for role in role_props:
                    if 'role' in role:
                        role_name = role['role']['roleName'].lower()
                        role_id = role['role']['roleId']
                        roles[role_name] = role_id

                return roles
            else:
                raise SDKException('Response', '102')
        else:
            response_string = self._commcell_object._update_response_(response.text)
            raise SDKException('Response', '101', response_string)

    def _add_security_association(self, association_list, user=False):
        """Adds the security association on the specified class object"""
        security_association_list = []
        for association in association_list:
            if not isinstance(association, dict):
                raise SDKException('Security', '101')

            if not self.has_role(association['role_name']):
                raise SDKException(
                    'Security', '102', 'Role {0} doesn\'t exist'.format(association['role_name'])
                )

            user_or_group = {}
            if user:
                user_or_group = {
                    "_type_": 13,
                    'userName': association['user_name']
                }

            temp = {
                "userOrGroup": [
                    user_or_group
                ],
                "properties": {
                    "role": {
                        "_type_": 120,
                        "roleId": self._roles[association['role_name'].lower()],
                        'roleName': association['role_name']
                    }
                }
            }
            security_association_list.append(temp)

        request_json = {
            "entityAssociated": self._entity_list,
            "securityAssociations": {
                "associationsOperationType": 1,
                "associations": security_association_list,
                "ownerAssociations": {
                    "ownersOperationType": 1
                }
            }
        }

        ADD_SECURITY_ASSOCIATION = self._commcell_object._services['SECURITY_ASSOCIATION']

        flag, response = self._commcell_object._cvpysdk_object.make_request(
            'POST', ADD_SECURITY_ASSOCIATION, request_json
        )

        if flag:
            if response.json() and 'response' in response.json():
                response_json = response.json()['response'][0]

                error_code = response_json['errorCode']

                if error_code != 0:
                    error_message = response_json['errorString']
                    raise SDKException(
                        'Security',
                        '102',
                        'Failed to add associations. \nError: {0}'.format(error_message)
                    )
            else:
                raise SDKException('Response', '102')
        else:
            response_string = self._commcell_object._update_response_(response.text)
            raise SDKException('Response', '101', response_string)

    def has_role(self, role_name):
        """Checks if role with specified name exists

            Args:
                role_name     (str)     --     name of the role to be verified

            Returns:
                (bool)     -  True if role with specified name exists
        """
        if not isinstance(role_name, basestring):
            raise SDKException('Security', '101')

        return self._roles and role_name.lower() in self._roles

