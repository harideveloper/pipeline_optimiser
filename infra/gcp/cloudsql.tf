

# # -----------------------
# # Cloud SQL instance with private IP
# # -----------------------
# resource "google_sql_database_instance" "postgres_instance" {
#   name             = "optimiser-db"
#   database_version = "POSTGRES_15"
#   region           = var.region

#   settings {
#     tier = "db-f1-micro"

#     ip_configuration {
#       ipv4_enabled    = false
#       private_network = google_compute_network.vpc.id
#     }
#   }

#   depends_on = [google_service_networking_connection.private_vpc_connection]
# }


