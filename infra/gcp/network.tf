
# # -----------------------
# # Networking
# # -----------------------
# resource "google_compute_network" "vpc" {
#   name = "optimiser-vpc"
# }

# resource "google_compute_subnetwork" "subnet" {
#   name          = "optimiser-subnet"
#   ip_cidr_range = "10.0.0.0/24"
#   region        = var.region
#   network       = google_compute_network.vpc.id
# }

# # -----------------------
# # Reserve IP range for private services connection
# # -----------------------
# resource "google_compute_global_address" "private_ip_range" {
#   name          = "sql-private-ip-range"
#   purpose       = "VPC_PEERING"
#   address_type  = "INTERNAL"
#   prefix_length = 16
#   network       = google_compute_network.vpc.id
#   project       = var.project_id
# }

# # -----------------------
# # Create VPC peering to servicenetworking.googleapis.com
# # -----------------------
# resource "google_service_networking_connection" "private_vpc_connection" {
#   network                 = google_compute_network.vpc.id
#   service                 = "servicenetworking.googleapis.com"
#   reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
#   project                  = var.project_id
# }
