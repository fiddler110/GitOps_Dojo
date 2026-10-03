package main

import rego.v1

allowed_regions := {"canadacentral", "canadaeast"}

deny contains msg if {
	some rc in input.resource_changes
	some action in rc.change.actions
	action in {"create", "update"}
	loc := rc.change.after.location
	loc != "" # only things that have a region: policy objects come through with ""
	not loc in allowed_regions
	msg := sprintf("%s uses region %s; allowed: %s", [rc.address, loc, concat(", ", sort(allowed_regions))])
}
