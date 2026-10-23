#!/usr/bin/env python3
"""
ContextFuse – AWS DynamoDB Table Provisioner.

Provisions the 'contextfuse-runs' table using PAY_PER_REQUEST (On-Demand)
billing so no ongoing capacity costs are incurred.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "contextfuse-runs")
REGION = os.getenv("AWS_REGION", "us-east-1")


def create_table():
    print(f"Connecting to DynamoDB in region '{REGION}'...")
    dynamodb = boto3.client("dynamodb", region_name=REGION)

    try:
        dynamodb.describe_table(TableName=TABLE_NAME)
        print(f"Table '{TABLE_NAME}' already exists and is active.")
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            print(f"Error checking table: {exc}")
            sys.exit(1)

    print(f"Creating table '{TABLE_NAME}'...")
    try:
        response = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "run_id", "KeyType": "HASH"},  # Partition Key
            ],
            AttributeDefinitions=[
                {"AttributeName": "run_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            Tags=[
                {"Key": "Project", "Value": "ContextFuse"},
                {"Key": "Environment", "Value": "Production"},
            ],
        )
        print(f"Table creation initiated: {response['TableDescription']['TableStatus']}")
        waiter = dynamodb.get_waiter("table_exists")
        print("Waiting for table to become ACTIVE...")
        waiter.wait(TableName=TABLE_NAME)
        print(f"Table '{TABLE_NAME}' is now ACTIVE and ready for use!")
    except Exception as exc:
        print(f"Failed to create DynamoDB table: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    create_table()
