resource "aws_sqs_queue" "events" {
  name                        = "${var.project_name}-events.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 60
}
