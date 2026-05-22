resource "aws_dynamodb_table" "loads" {
  name         = "${var.project_name}-loads"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "load_id"

  attribute {
    name = "load_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "events" {
  name         = "${var.project_name}-events"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "load_id"
  range_key    = "event_id"

  attribute {
    name = "load_id"
    type = "S"
  }
  attribute {
    name = "event_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "tool_calls" {
  name         = "${var.project_name}-tool-calls"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "load_id"
  range_key    = "sort_key"

  attribute {
    name = "load_id"
    type = "S"
  }
  attribute {
    name = "sort_key"
    type = "S"
  }
}
