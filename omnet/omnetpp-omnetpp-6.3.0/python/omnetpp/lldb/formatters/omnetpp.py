# invoke from LLDB with: command script import <OMNETPP_ROOT>/python/omnetpp/lldb/formatters/omnetpp.py

import lldb
from decimal import *

def cDisplayString_SummaryProvider(value, internal_dict):
    child = value.GetChildMemberWithName("assembledString")
    if child is None or not child.IsValid():
        return "<invalid>"
    summary = child.GetSummary()
    if summary is None or len(summary) < 2:
        return "<invalid>"
    return summary[1:-1]

def simtime_t_SummaryProvider(value, internal_dict):
    t_child = value.GetChildMemberWithName("t")
    if t_child is None or not t_child.IsValid():
        return "invalid"
    t_value = t_child.GetValue()
    if t_value is None or t_value == "":
        return "invalid"

    if t_value == "0":
        return "0s"
    scaleexp = value.GetTarget().FindFirstGlobalVariable("omnetpp::SimTime::scaleexp").GetValueAsSigned()
    s = Decimal(str(t_value) + 'E' + str(scaleexp)).normalize()
    return str(s) + "s"

def cNamedObject_SummaryProvider(value, internal_dict):
    child = value.GetChildMemberWithName("name")
    if child is None or not child.IsValid():
        return "<invalid>"
    summary = child.GetSummary()
    if summary is None or len(summary) < 2:
        return "<invalid>"
    return summary[1:-1]

def cOwnedObject_SummaryProvider(value, internal_dict):
    name_child = value.GetChildMemberWithName("name")
    owner_child = value.GetChildMemberWithName("owner")

    if name_child is None or not name_child.IsValid():
        name_str = "<invalid>"
    else:
        name_summary = name_child.GetSummary()
        name_str = name_summary[1:-1] if name_summary and len(name_summary) >= 2 else "<invalid>"

    if owner_child is None or not owner_child.IsValid():
        owner_str = "<invalid>"
    else:
        owner_str = owner_child.GetSummary() or "<invalid>"

    return f"{name_str} (owned by {owner_str})"

def cModule_SummaryProvider(value, internal_dict):
    type_child = value.GetChildMemberWithName("componentType")
    path_child = value.GetChildMemberWithName("fullPath")

    if type_child is None or not type_child.IsValid():
        type_str = "<invalid>"
    else:
        type_summary = type_child.GetSummary()
        type_str = type_summary[1:-1] if type_summary and len(type_summary) >= 2 else "<invalid>"

    if path_child is None or not path_child.IsValid():
        path_str = "<invalid>"
    else:
        path_summary = path_child.GetSummary()
        path_str = path_summary[1:-1] if path_summary and len(path_summary) >= 2 else "<invalid>"

    return f"({type_str}) {path_str}"

def cComponentType_SummaryProvider(value, internal_dict):
    child = value.GetChildMemberWithName("qualifiedName")
    if child is None or not child.IsValid():
        return "<invalid>"
    summary = child.GetSummary()
    return summary if summary else "<invalid>"

def cComponent_SummaryProvider(value, internal_dict):
    name_child = value.GetChildMemberWithName("name")
    type_child = value.GetChildMemberWithName("componentType")

    if name_child is None or not name_child.IsValid():
        name_str = "<invalid>"
    else:
        name_summary = name_child.GetSummary()
        name_str = name_summary[1:-1] if name_summary and len(name_summary) >= 2 else "<invalid>"

    if type_child is None or not type_child.IsValid():
        type_str = "<invalid>"
    else:
        type_summary = type_child.GetSummary()
        type_str = type_summary[1:-1] if type_summary and len(type_summary) >= 2 else "<invalid>"

    return f"{name_str}: {type_str}"

def cEvent_SummaryProvider(value, internal_dict):
    name_child = value.GetChildMemberWithName("name")
    time_child = value.GetChildMemberWithName("arrivalTime")
    priority_child = value.GetChildMemberWithName("priority")

    if name_child is None or not name_child.IsValid():
        name_str = "<invalid>"
    else:
        name_summary = name_child.GetSummary()
        name_str = name_summary[1:-1] if name_summary and len(name_summary) >= 2 else "<invalid>"

    if time_child is None or not time_child.IsValid():
        time_str = "<invalid>"
    else:
        time_str = time_child.GetSummary() or "<invalid>"

    if priority_child is None or not priority_child.IsValid():
        priority_str = "<invalid>"
    else:
        priority_str = priority_child.GetValue() or "<invalid>"

    return f"{name_str} @{time_str} pri:{priority_str}"

def cMessage_SummaryProvider(value, internal_dict):
    id_child = value.GetChildMemberWithName("messageId")
    kind_child = value.GetChildMemberWithName("messageKind")

    if id_child is None or not id_child.IsValid():
        id_str = "<invalid>"
    else:
        id_str = id_child.GetValue() or "<invalid>"

    if kind_child is None or not kind_child.IsValid():
        kind_str = "<invalid>"
    else:
        kind_str = kind_child.GetValue() or "<invalid>"

    return f"#{id_str} {cEvent_SummaryProvider(value, internal_dict)} kind:{kind_str}"

def cPacket_SummaryProvider(value, internal_dict):
    length_child = value.GetChildMemberWithName("bitLength")
    duration_child = value.GetChildMemberWithName("duration")

    if length_child is None or not length_child.IsValid():
        length_str = "<invalid>"
    else:
        length_str = length_child.GetValue() or "<invalid>"

    if duration_child is None or not duration_child.IsValid():
        duration_str = "<invalid>"
    else:
        duration_str = duration_child.GetSummary() or "<invalid>"

    return f"{cMessage_SummaryProvider(value, internal_dict)} len:{length_str}bit dur:{duration_str}"

def __lldb_init_module(debugger, internal_dict):
    print("Initializing LLDB type formatters for OMNeT++")
    debugger.HandleCommand("type summary add -w omnetpp --summary-string ${var%s} char[]")
    debugger.HandleCommand("type summary add -w omnetpp -v --summary-string #${var} omnetpp::msgid_t")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.simtime_t_SummaryProvider omnetpp::simtime_t")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cDisplayString_SummaryProvider omnetpp::cDisplayString")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cNamedObject_SummaryProvider omnetpp::cNamedObject")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cOwnedObject_SummaryProvider omnetpp::cOwnedObject")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cOwnedObject_SummaryProvider omnetpp::cNoncopyableOwnedObject")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cOwnedObject_SummaryProvider omnetpp::cDefaultOwner")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cComponentType_SummaryProvider omnetpp::cComponentType")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cComponentType_SummaryProvider omnetpp::cModuleType")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cComponentType_SummaryProvider omnetpp::cDynamicModuleType")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cComponent_SummaryProvider omnetpp::cComponent")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cModule_SummaryProvider omnetpp::cModule")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cModule_SummaryProvider omnetpp::cSimpleModule")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cEvent_SummaryProvider omnetpp::cEvent")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cMessage_SummaryProvider omnetpp::cMessage")
    debugger.HandleCommand(f"type summary add -w omnetpp -v -F {__name__}.cPacket_SummaryProvider omnetpp::cPacket")
    debugger.HandleCommand("type category enable omnetpp")