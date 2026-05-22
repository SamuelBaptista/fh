resource "aws_ecr_repository" "app" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api"
  role          = aws_iam_role.api_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:latest"
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      API_TOKEN                 = var.api_token
      OPEN_ROUTER_API_KEY       = var.open_router_api_key
      SQS_QUEUE_URL             = aws_sqs_queue.events.url
      DYNAMODB_LOADS_TABLE      = aws_dynamodb_table.loads.name
      DYNAMODB_EVENTS_TABLE     = aws_dynamodb_table.events.name
      DYNAMODB_TOOL_CALLS_TABLE = aws_dynamodb_table.tool_calls.name
      AWS_LWA_INVOKE_MODE       = "response_stream"
    }
  }
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_function" "worker" {
  function_name = "${var.project_name}-worker"
  role          = aws_iam_role.worker_lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:latest"
  timeout       = 60
  memory_size   = 512

  environment {
    variables = {
      HANDLER                   = "worker"
      OPEN_ROUTER_API_KEY       = var.open_router_api_key
      SQS_QUEUE_URL             = aws_sqs_queue.events.url
      DYNAMODB_LOADS_TABLE      = aws_dynamodb_table.loads.name
      DYNAMODB_EVENTS_TABLE     = aws_dynamodb_table.events.name
      DYNAMODB_TOOL_CALLS_TABLE = aws_dynamodb_table.tool_calls.name
      SCHEDULER_ROLE_ARN        = aws_iam_role.scheduler.arn
      SCHEDULER_TARGET_ARN      = aws_sqs_queue.events.arn
    }
  }
}

resource "aws_lambda_event_source_mapping" "worker_sqs" {
  event_source_arn = aws_sqs_queue.events.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1
  enabled          = true
}
