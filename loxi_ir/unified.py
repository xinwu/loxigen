#!/usr/bin/env python
# Copyright 2013, Big Switch Networks, Inc.
#
# LoxiGen is licensed under the Eclipse Public License, version 1.0 (EPL), with
# the following special exception:
#
# LOXI Exception
#
# As a special exception to the terms of the EPL, you may distribute libraries
# generated by LoxiGen (LoxiGen Libraries) under the terms of your choice, provided
# that copyright and licensing notices generated by LoxiGen are not altered or removed
# from the LoxiGen Libraries and the notice provided below is (i) included in
# the LoxiGen Libraries, if distributed in source code form and (ii) included in any
# documentation for the LoxiGen Libraries, if distributed in binary form.
#
# Notice: "Copyright 2013, Big Switch Networks, Inc. This library was generated by the LoxiGen Compiler."
#
# You may not use this file except in compliance with the EPL or LOXI Exception. You may obtain
# a copy of the EPL at:
#
# http://www.eclipse.org/legal/epl-v10.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# EPL for the specific language governing permissions and limitations
# under the EPL.

import copy
from collections import OrderedDict
from itertools import chain
import logging

import ir

def build_unified_ir(name_protocol_map):
    class UnifiedClassSpec(object):
        def __init__(self, name):
            self.name = name
            self.members = OrderedDict()
            self.superclass_name = None
            self.superclass_set = False
            self.params = OrderedDict()
            self.version_class = OrderedDict()
            self.virtual = False
            self.base_length = None
            self.is_fixed_length = True

        def add_class(self, version, v_class):
            for v_member in v_class.members:
                if hasattr(v_member, "name"):
                    if not v_member.name in self.members:
                        self.members[v_member.name] = v_member
                    else:
                        if not type(self.members[v_member.name]) == type(v_member):
                            raise Exception("Error unifying ir class {} - adding version: {} - member_type {} <-> {}".format(
                                    self.name, v_class.protocol.version, self.members[v_member.name], v_member))

            if not self.superclass_set:
                self.superclass_name = v_class.superclass.name if v_class.superclass else None
            else:
                if self.superclass_name != v_class.superclass_name:
                    raise Exception("Error unifying ir class {} - adding version {} - superclass: param {} <-> {}".format(
                            self.name, v_class.protocol.version, self.superclass_name, v_class.superclass_name))

            for name, value in v_class.params.items():
                if not name in self.params:
                    self.params[name] = value
                else:
                    if self.params[name] != value:
                        raise Exception("Error unifying ir class {} - adding version: {} - param {} <-> {}".format(
                                self.name, v_class.protocol.version, self.params[name], value))

            if v_class.virtual:
                self.virtual = True

            if not v_class.is_fixed_length:
                self.is_fixed_length = False

            if self.base_length is None:
                self.base_length = v_class.base_length
            elif self.base_length != v_class.base_length:
                self.is_fixed_length = False
                if self.base_length > v_class.base_length:
                    self.base_length = v_class.base_length
            self.version_class[version] = v_class

    class UnifiedEnumSpec(object):
        def __init__(self, name):
            self.name = name
            self.entries = {}
            self.params = {}
            self.version_enums = OrderedDict()

        def add_enum(self, version, v_enum):
            for e in v_enum.entries:
                if not e.name in self.entries:
                    self.entries[e.name] = ir.OFEnumEntry(e.name, e.value, copy.copy(e.params))
                else:
                    entry = self.entries[e.name]
                    for name, value in e.params.items():
                        if not name in entry.params:
                            entry.params[name] = value
                        elif entry.params[name] != value:
                            raise Exception("Error unifying ir enum {} - adding version: param {} <-> {}".format(
                                self.name, entry.params[name], value))
            for name, value in v_enum.params.items():
                if not name in self.params:
                    self.params[name] = value
                else:
                    if self.params[name] != value:
                        if name == "wire_type":
                            self.params[name] = None
                        else:
                            raise Exception("Error unifying ir enum {} - adding version: {} param {} <-> {}".format(
                                self.name, v_enum.protocol.version, self.params[name], value))

            self.version_enums[version]=v_enum

    u_name_classes = OrderedDict()
    u_name_enums = OrderedDict()

    for version, protocol in name_protocol_map.items():
        assert isinstance(version, ir.OFVersion)
        for v_class in protocol.classes:
            name = v_class.name
            if not name in u_name_classes:
                u_name_classes[name] = UnifiedClassSpec(name)
            spec = u_name_classes[name]
            spec.add_class(version, v_class)

        for v_enum in protocol.enums:
            name = v_enum.name
            if not name in u_name_enums:
                u_name_enums[name] = UnifiedEnumSpec(name)
            spec = u_name_enums[name]
            spec.add_enum(version, v_enum)

    unified_enums = tuple(ir.OFEnum(name=s.name, entries=tuple(s.entries.values()), params=s.params) for s in u_name_enums.values())
    unified_classes = OrderedDict()
    for name, spec in u_name_classes.items():
        u = ir.OFUnifiedClass(
                name = spec.name,
                version_classes=spec.version_class,
                superclass=None if not spec.superclass_name else unified_classes[spec.superclass_name],
                members=spec.members.values(),
                virtual=spec.virtual,
                params=spec.params,
                base_length=spec.base_length,
                is_fixed_length=spec.is_fixed_length)
        unified_classes[name] = u

    unified = ir.OFProtocol(version=None, classes = tuple(unified_classes.values()), enums=unified_enums)
    for e in chain(unified.classes, unified.enums):
        e.protocol = unified
    return unified
