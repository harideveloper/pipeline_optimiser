# # -----------------------
# # Enable Required APIs
# # -----------------------
# resource "google_project_service" "required_apis" {
#   for_each = toset([
#     "artifactregistry.googleapis.com",
#     "run.googleapis.com",
#     "cloudbuild.googleapis.com",
#     "sqladmin.googleapis.com",
#     "secretmanager.googleapis.com",
#     "compute.googleapis.com",
#     "vpcaccess.googleapis.com"
#   ])

#   project = var.project_id
#   service = each.key

#   disable_on_destroy = false
# }
