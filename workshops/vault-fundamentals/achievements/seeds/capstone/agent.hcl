# Starter Agent config for the capstone. Fill it in; keep every credential out of this file.
vault {
  address = "http://openbao:8200"
}

auto_auth {
  # method "jwt" { ... } : the platform identity, not a stored secret
}
