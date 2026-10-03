package main

import rego.v1

GOOD := `{"resource_changes":[{"address":"a","change":{"actions":["create"],"after":{"location":"canadacentral","tags":{"costCenter":"cc-1"}}}}]}`

BAD := `{"resource_changes":[{"address":"a","change":{"actions":["create"],"after":{"location":"canadacentral","tags":{"owner":"x"}}}}]}`

test_good_plan_passes if {
	count(deny) == 0 with input as json.unmarshal(GOOD)
}

test_bad_plan_denied if {
	count(deny) > 0 with input as json.unmarshal(BAD)
}

test_update_without_tag_denied if {
	deny["azurerm_resource_group.x is missing the costCenter tag"] with input as {"resource_changes": [{
		"address": "azurerm_resource_group.x",
		"change": {"actions": ["update"], "after": {"tags": {"owner": "a"}}},
	}]}
}

test_delete_ignored if {
	count(deny) == 0 with input as {"resource_changes": [{
		"address": "azurerm_resource_group.x",
		"change": {"actions": ["delete"], "after": null},
	}]}
}

test_resource_without_tags_attribute_ignored if {
	count(deny) == 0 with input as {"resource_changes": [{
		"address": "azurerm_policy_definition.x",
		"change": {"actions": ["create"], "after": {"name": "x"}},
	}]}
}

test_null_tags_denied if {
	count(deny) == 1 with input as {"resource_changes": [{
		"address": "azurerm_resource_group.x",
		"change": {"actions": ["create"], "after": {"tags": null}},
	}]}
}
