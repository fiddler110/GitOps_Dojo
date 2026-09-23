# The resources: what should exist. Each block is `resource "<type>" "<name>"`.
# The type (random_pet) picks the provider; the name (nickname) is just how
# other blocks refer to it.

# 1. A random name. Generated once, then remembered in state.
resource "random_pet" "nickname" {
  length = var.pet_words
}

# 2. A file on disk. It uses the name above, so OpenTofu knows to create the
#    pet BEFORE the file — you never write that ordering down yourself.
resource "local_file" "greeting" {
  filename        = "${path.module}/out/hello.txt"
  content         = "${var.greeting}\nFrom: ${var.learner} (${random_pet.nickname.id})\n"
  file_permission = "0644"
}

# 3. terraform_data: a built-in resource that just stores a value in state.
#    Handy for seeing how plan reacts when an input changes.
resource "terraform_data" "note" {
  input = "Deployed by ${var.learner}"
}
