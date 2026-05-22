output "api_url" {
  value = aws_lambda_function_url.api.function_url
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "sqs_queue_url" {
  value = aws_sqs_queue.events.url
}
