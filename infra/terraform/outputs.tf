output "api_url" {
  value = "http://${aws_lb.api.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "sqs_queue_url" {
  value = aws_sqs_queue.events.url
}
