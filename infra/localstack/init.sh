#!/bin/bash
set -e

awslocal sqs create-queue \
  --queue-name watchtower-events.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true

awslocal dynamodb create-table \
  --table-name watchtower-loads \
  --key-schema AttributeName=load_id,KeyType=HASH \
  --attribute-definitions AttributeName=load_id,AttributeType=S \
  --billing-mode PAY_PER_REQUEST

awslocal dynamodb create-table \
  --table-name watchtower-events \
  --key-schema AttributeName=load_id,KeyType=HASH AttributeName=event_id,KeyType=RANGE \
  --attribute-definitions AttributeName=load_id,AttributeType=S AttributeName=event_id,AttributeType=S \
  --billing-mode PAY_PER_REQUEST

awslocal dynamodb create-table \
  --table-name watchtower-tool-calls \
  --key-schema AttributeName=load_id,KeyType=HASH AttributeName=sort_key,KeyType=RANGE \
  --attribute-definitions AttributeName=load_id,AttributeType=S AttributeName=sort_key,AttributeType=S \
  --billing-mode PAY_PER_REQUEST

echo "LocalStack init complete"
