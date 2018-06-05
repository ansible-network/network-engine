# network_engine filter plugins

The [filter_plugins/network_engine](https://github.com/ansible-network/network-engine/blob/devel/library/filter_plugins/network_engine.py)
code offers four options for managing multiple interfaces and vlans.

## interface_split

The `interface_split` plugin splits an interface and returns its parts:

{{ 'Ethernet1-2' | interface_split }} returns ['Ethernet1', 'Ethernet2']
{{ 'Ethernet1' | interface_split('name') }} returns Ethernet
{{ 'Ethernet1' | interface_split('index') }} returns 1

## interface_range

The `interface_range` plugin expands an interface range and returns a list of the interfaces within that range:

{{ 'Ethernet1-3' | interface_range }} returns ['Ethernet1', 'Ethernet2', 'Ethernet3']
{{ 'Ethernet1,3-4,5' | interface_range }} returns ['Ethernet1', 'Ethernet3', 'Ethernet4', 'Ethernet5']

## vlan_compress

The `vlan_compress` plugin compresses a list of vlans into a range: 

{{ 'vlan1,2,3,4,5' | vlan_compress }} returns ['vlan1-5']
{{ 'vlan1,2,4,5' | vlan_compress }} returns ['vlan1-2,4-5']
{{ 'vlan1,2,3,5' | vlan_compress }} returns ['vlan1-3,5']

## vlan_expand

The `vlan_expand` plugin expands a vlan range and returns a list of the vlans within that range:

{{ 'vlan1,3-5,7' | vlan_expand }} returns ['vlan1,3,4,5,7']
{{ 'vlan1-5' | vlan_expand }} returns ['vlan1,2,3,4,5']
