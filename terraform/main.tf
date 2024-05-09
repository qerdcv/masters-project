provider "digitalocean" {
  token = var.do_token
}


resource "digitalocean_droplet" "web" {
  name   = "web-server"
  image  = "ubuntu-20-04-x64"
  region = "fra1"
  size   = "s-1vcpu-1gb"
  ssh_keys = [data.digitalocean_ssh_key.deploy.id]
}


variable "do_token" {
  description = "DO api token"
  type = string
}

output server_ip {
  value = digitalocean_droplet.web.ipv4_address 

}


# resource "digitalocean_ssh_key" "deploy" {
#   name       = "deployment_key_new"
#   public_key = file("~/.ssh/id_rsa.pub")
# }



terraform {
  required_providers {
    digitalocean = {
      source = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}



resource "digitalocean_loadbalancer" "ltiserv_lb" {
  name   = "lti-lb"
  region = "fra1"

  forwarding_rule {
    entry_port     = 80
    entry_protocol = "http"

    target_port     = 8000  # Port your Flask app is running on
    target_protocol = "http"
  }

  healthcheck {
    port     = 8000  # Port your Flask app is running on
    protocol = "http"
    path = "/"
  }

  droplet_ids = [
    digitalocean_droplet.web.id,
  ]
}


data "digitalocean_ssh_key" "deploy" {
  name = "deployment_key"
}