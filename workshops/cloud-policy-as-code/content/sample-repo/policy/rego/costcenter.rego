package main

import rego.v1

# Lab 9: refuse any created or updated resource without a costCenter tag. Resources with no tags
# attribute at all (policy objects, for example) are not tagged things, so they are skipped.
deny contains msg if {
	some rc in input.resource_changes
	some action in rc.change.actions
	action in {"create", "update"}
	tags := rc.change.after.tags
	not tags.costCenter
	msg := sprintf("%s is missing the costCenter tag", [rc.address])
}
