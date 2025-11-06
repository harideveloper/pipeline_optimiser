# resource "google_sql_database" "optimiser_db" {
#   name     = var.DB_NAME
#   instance = google_sql_database_instance.postgres_instance.name
# }

# resource "google_sql_user" "optimiser_user" {
#   name     = var.DB_USER
#   instance = google_sql_database_instance.postgres_instance.name
#   password = var.DB_PASS
# }
