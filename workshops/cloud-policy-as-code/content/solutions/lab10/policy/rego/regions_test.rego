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

test_prefix_lookalike_denied if {
	count(deny) == 1 with input as rc("canadawest")
}

test_central_allowed if {
	count(deny) == 0 with input as rc("canadacentral")
}

test_delete_ignored if {
	count(deny) == 0 with input as {"resource_changes": [{
		"address": "azurerm_resource_group.x",
		"change": {"actions": ["delete"], "after": null},
	}]}
}

test_near_misses_denied if {
	every loc in ["eastus", "westeurope", "canada", "canadacentral2", ""] {
		count(deny) == 1 with input as rc(loc)
	}
}
