#!/usr/bin/env python3

# Copyright (c) 2021 Seagate Technology LLC and/or its Affiliates
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>. For any questions
# about this software or licensing, please email opensource@seagate.com or
# cortx-questions@seagate.com.


import time

from ha.monitor.k8s.error import NotSupportedObjectError
from ha.monitor.k8s.const import K8SEventsConst
from ha.monitor.k8s.const import AlertStates
from ha.monitor.k8s.const import EventStates
from ha.monitor.k8s.alert import K8sAlert
from ha import const
from ha.const import _DELIM

from cortx.utils.log import Log
from cortx.utils.conf_store import Conf

class ObjectParser:
    def __init__(self):
        pass

    def parse(self, an_event, cached_state):
        pass


class NodeEventParser(ObjectParser):
    def __init__(self):
        super().__init__()
        self._type = 'host'

    def parse(self, an_event, cached_state):
        alert = K8sAlert()
        alert.resource_type = self._type
        alert.timestamp = str(int(time.time()))

        if K8SEventsConst.TYPE in an_event:
            alert.event_type = an_event[K8SEventsConst.TYPE]
        if K8SEventsConst.NAME in an_event[K8SEventsConst.RAW_OBJECT][K8SEventsConst.METADATA]:
            alert.resource_name = an_event[K8SEventsConst.RAW_OBJECT][K8SEventsConst.METADATA][K8SEventsConst.NAME]

        ready_status = None
        try:
            for a_condition in an_event[K8SEventsConst.RAW_OBJECT][K8SEventsConst.STATUS][K8SEventsConst.CONDITIONS]:
                if a_condition[K8SEventsConst.TYPE] == K8SEventsConst.READY:
                    ready_status = a_condition[K8SEventsConst.STATUS]
        except Exception as e:
            Log.warn(f"Exception received during parsing {e}")

        if ready_status is None:
            Log.debug(f"ready_status is None for node resource {alert.resource_name}")
            cached_state[alert.resource_name] = ready_status
            return None

        if alert.event_type == EventStates.ADDED:
            cached_state[alert.resource_name] = ready_status.lower()
            if ready_status.lower() == K8SEventsConst.true:
                alert.event_type = AlertStates.ONLINE
                return alert
            else:
                Log.debug(f"[EventStates ADDED] No change detected for node resource {alert.resource_name}")
                return None

        if alert.event_type == EventStates.MODIFIED:
            if alert.resource_name in cached_state:
                if cached_state[alert.resource_name] != K8SEventsConst.true and ready_status.lower() == K8SEventsConst.true:
                    cached_state[alert.resource_name] = ready_status.lower()
                    alert.event_type = AlertStates.ONLINE
                    return alert
                elif cached_state[alert.resource_name] == K8SEventsConst.true and ready_status.lower() != K8SEventsConst.true:
                    cached_state[alert.resource_name] = ready_status.lower()
                    alert.event_type = AlertStates.FAILED
                    return alert
                else:
                    Log.debug(f"[EventStates MODIFIED] No change detected for node resource {alert.resource_name}")
                    return None
            else:
                Log.debug(f"[EventStates MODIFIED] No cached state detected for node resource {alert.resource_name}")
                return None

        # Handle DELETED event - Not required for Cortx

        return None


class PodEventParser(ObjectParser):
    def __init__(self):
        super().__init__()
        self._type = 'node'

    def parse(self, an_event, cached_state):
        alert = K8sAlert()
        alert.resource_type = self._type
        alert.timestamp = str(int(time.time()))

        # Imp Note: Below logic is required only if we are getting the absolute path where the machine-id exists in the event.
        #           i.e. metadata/podInfo/machineId so it will be parsed like [raw_object][metadata][podInfo][machineId]
        #           because k8s event we receive is multi-level nested dict and  the key can occur at multiple places
        #           for different reasons as other many keys getting repeated so choosing required key will be difficult.
        #           OR if once the key is added while creating pod and the fixed exact location in the event is found then,
        #           the changes added in /k8s_setup/ha_setup.py for this key and the below logic for parsing this key
        #           is also not required can add constant and directly fetch the value.

        # Get value of machine id key (path of the machine id in k8s event)
        machine_id_key = Conf.get(const.HA_GLOBAL_INDEX, f"MONITOR{_DELIM}machine_id_key")

        # loop over keys and check if exist then get the value.
        # this code is flexible can be used for any key in event for example
        # if value at the place event[raw_object][metadata][name] then input key will be 'metadata/name'
        # note if the key is fixed cannot chnage then can use constant here also insted of parsing
        machine_id_keys = machine_id_key.split('/')
        machine_id = an_event[K8SEventsConst.RAW_OBJECT]
        for key in machine_id_keys:
            if key != None and isinstance(machine_id, dict) and key in machine_id:
                machine_id = machine_id[key]
        if  machine_id is not None and not isinstance(machine_id, dict):
            alert.resource_name = machine_id

        if K8SEventsConst.TYPE in an_event:
            alert.event_type = an_event[K8SEventsConst.TYPE]
        if K8SEventsConst.NODE_NAME in an_event[K8SEventsConst.RAW_OBJECT][K8SEventsConst.SPEC]:
            alert.node = an_event[K8SEventsConst.RAW_OBJECT][K8SEventsConst.SPEC][K8SEventsConst.NODE_NAME]

        ready_status = None
        try:
            for a_condition in an_event[K8SEventsConst.RAW_OBJECT][K8SEventsConst.STATUS][K8SEventsConst.CONDITIONS]:
                if a_condition[K8SEventsConst.TYPE] == K8SEventsConst.READY:
                    ready_status = a_condition[K8SEventsConst.STATUS]
        except Exception as e:
            Log.warn(f"Exception received during parsing {e}")

        if ready_status is None:
            Log.debug(f"ready_status is None for pod resource {alert.resource_name}")
            cached_state[alert.resource_name] = ready_status
            return None

        if an_event[K8SEventsConst.TYPE] == EventStates.ADDED:
            cached_state[alert.resource_name] = ready_status.lower()
            if ready_status.lower() != K8SEventsConst.true:
                Log.debug(f"[EventStates ADDED] No change detected for pod resource {alert.resource_name}")
                return None
            else:
                alert.event_type = AlertStates.ONLINE
                return alert

        if alert.event_type == EventStates.MODIFIED:
            if alert.resource_name in cached_state:
                if cached_state[alert.resource_name] != K8SEventsConst.true and ready_status.lower() == K8SEventsConst.true:
                    cached_state[alert.resource_name] = ready_status.lower()
                    alert.event_type = AlertStates.ONLINE
                    return alert
                elif cached_state[alert.resource_name] == K8SEventsConst.true and ready_status.lower() != K8SEventsConst.true:
                    cached_state[alert.resource_name] = ready_status.lower()
                    alert.event_type = AlertStates.FAILED
                    return alert
                else:
                    Log.debug(f"[EventStates MODIFIED] No change detected for pod resource {alert.resource_name}")
                    return None
            else:
                Log.debug(f"[EventStates MODIFIED] No cached state detected for pod resource {alert.resource_name}")
                return None

        # Handle DELETED event - Not required for Cortx

        return None


class EventParser:
    parser_map = {
        'node': NodeEventParser(),
        'pod': PodEventParser()
    }

    @staticmethod
    def parse(k_object, an_event, cached_state):
        if k_object in EventParser.parser_map:
            object_event_parser = EventParser.parser_map[k_object]
            return object_event_parser.parse(an_event, cached_state)

        raise NotSupportedObjectError(f"object = {k_object}")

