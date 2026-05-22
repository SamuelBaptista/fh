variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "watchtower-mini"
}

variable "open_router_api_key" {
  sensitive = true
}

variable "api_token" {
  sensitive = true
}
