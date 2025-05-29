output "app_name" {
  value = juju_application.feast_integrator.name
}

output "provides" {
  value = {
    feast_configuration = "feast-configuration",
  }
}

output "requires" {
  value = {
    offline_store = "offline-store",
    online_store  = "online_store",
    registry      = "registry",
    secrets       = "secrets",
    pod_defaults  = "pod-defaults",
  }
}
