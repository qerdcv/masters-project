provider "digitalocean" {
  token = "
  "
}


resource "digitalocean_droplet" "web" {
  name   = "web-server"
  image  = "ubuntu-20-04-x64"
  region = "fra1"
  size   = "s-1vcpu-1gb"
  ssh_keys = [
    var.ssh_fingerprint
  ]
}


variable "ssh_fingerprint" {
  description = "The fingerprint of the SSH key"
}


output server_ip {
  value = digitalocean_droplet.web.ipv4_address 

}


resource "digitalocean_ssh_key" "del" {
  name       = "deployment_key"
  public_key = file("~/.ssh/id_rsa.pub")
}



terraform {
  required_providers {
    digitalocean = {
      source = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}