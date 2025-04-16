output "app_name" {
  value = juju_application.feast_integrator.name
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
