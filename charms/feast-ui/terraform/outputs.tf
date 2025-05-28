output "app_name" {
  value = juju_application.feast_ui.name
}


output "requires" {
  value = {
    feast_configuration = "feast-configuration",
    ingress             = "ingress",
    dashboard_links     = "dashboard-links",
  }
}
