# Outputs: values printed after `apply` and readable later with `tofu output`.

output "nickname" {
  description = "The generated pet name."
  value       = random_pet.nickname.id
}

output "greeting_file" {
  description = "Where the greeting was written."
  value       = local_file.greeting.filename
}
