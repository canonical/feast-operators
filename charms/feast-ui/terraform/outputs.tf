output "app_name" {
  value = juju_application.feast_ui.name
}


output "requires" {
  value = {
    feast-configuration = "feast-configuration",
    ingress             = "ingress",
    dashboard-links     = "dashboard-links",
  }
}
