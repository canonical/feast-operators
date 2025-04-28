resource "juju_application" "feast_integrator" {
  charm {
    name     = "feast-integrator"
    channel  = var.channel
    revision = var.revision
  }
  config = var.config
  model  = var.model_name
  name   = var.app_name
  trust  = true
  units  = 1
}
