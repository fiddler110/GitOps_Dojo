# Outputs: values printed after `apply` and readable later with `tofu output`.

output "resource_id" {
  description = "The full Azure-style resource ID of the container group."
  value       = azurerm_container_group.hello.id
}

output "fqdn" {
  description = "The container group's DNS name."
  value       = azurerm_container_group.hello.fqdn
}

output "url" {
  description = "Link to your running site (also reachable with Browse in the portal)."
  value       = "${var.portal_base_url}/site/${local.dns_label}/"
}
