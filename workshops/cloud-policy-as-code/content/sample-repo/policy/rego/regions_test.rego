package main

import rego.v1

rc(loc) := {"resource_changes": [{
	"address": "azurerm_resource_group.x",
	"change": {"actions": ["create"], "after": {"location": loc, "tags": {"costCenter": "1"}}},
}]}

test_canada_allowed if {
	count(deny) == 0 with input as rc("canadaeast")
}

test_other_region_denied if {
	count(deny) == 1 with input as rc("eastus")
}
