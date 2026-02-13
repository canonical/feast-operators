output "app_name" {
  value = juju_application.feast_ui.name
}

output "provides" {
  value = {
    provide_cmr_mesh = "provide-cmr-mesh",
  }
}

output "requires" {
  value = {
    dashboard_links     = "dashboard-links",
    feast_configuration = "feast-configuration",
    ingress             = "ingress",
    require_cmr_mesh    = "require-cmr-mesh",
    service_mesh        = "service-mesh",
  }
}
