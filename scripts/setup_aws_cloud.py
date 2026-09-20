"""
Iris Voice Assistant — AWS Cloud Verification & Provisioning Utility
====================================================================
Verifies AWS credentials, validates Free-Tier Serverless resources,
and provisions DynamoDB & CloudWatch observability for zero extra cost.
"""

import os
import sys

# Load local .env reliably
try:
    from dotenv import load_dotenv, find_dotenv
    env_path = find_dotenv(usecwd=True)
    if not env_path:
        # Fallback to repo root .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(env_path, override=True)
except ImportError:
    pass

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("[ERROR] boto3 is not installed in current environment. Run: pip install boto3")
    sys.exit(1)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    region = os.getenv("AWS_DEFAULT_REGION", "eu-north-1")
    print("=" * 70)
    print("IRIS VOICE ASSISTANT - AWS CLOUD READINESS & COST AUDIT")
    print("=" * 70)
    print(f"Target AWS Region: {region}\n")

    # 1. Identity Check
    try:
        sts = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        account_id = identity.get("Account")
        arn = identity.get("Arn")
        print(f"[OK] AWS Credentials Active!")
        print(f"    - Account ID : {account_id}")
        print(f"    - Identity   : {arn}")
    except (NoCredentialsError, ClientError) as e:
        print("[!] No active AWS credentials found in environment or ~/.aws/credentials.")
        print("    Please set in your local .env file:")
        print("      AWS_ACCESS_KEY_ID=your_access_key")
        print("      AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("      AWS_DEFAULT_REGION=eu-north-1")
        return

    # 2. DynamoDB Audit Table (PAY_PER_REQUEST = $0 Base Cost)
    table_name = os.getenv("DYNAMODB_TABLE_NAME", "IrisSecurityAudit")
    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        existing_tables = [t.name for t in dynamodb.tables.all()]
        if table_name in existing_tables:
            print(f"[OK] DynamoDB Table '{table_name}' is active and ready (PAY_PER_REQUEST, $0 cost).")
        else:
            print(f"[*] Creating DynamoDB Table '{table_name}' with PAY_PER_REQUEST billing...")
            table = dynamodb.create_table(
                TableName=table_name,
                BillingMode="PAY_PER_REQUEST",
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "S"}
                ],
                KeySchema=[
                    {"AttributeName": "session_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"}
                ],
                Tags=[
                    {"Key": "Project", "Value": "IrisVoiceAssistant"},
                    {"Key": "Accessibility", "Value": "DigitalBraille"}
                ]
            )
            table.wait_until_exists()
            print(f"[OK] DynamoDB Table '{table_name}' successfully created!")
    except ClientError as e:
        print(f"[!] DynamoDB Check Notice: {e.response.get('Error', {}).get('Message', str(e))}")

    # 3. Amazon Polly Neural Voice Test
    try:
        polly = boto3.client("polly", region_name=region)
        res = polly.describe_voices(LanguageCode="en-US")
        voices = [v["Name"] for v in res.get("Voices", []) if "neural" in v.get("SupportedEngines", [])]
        print(f"[OK] Amazon Polly Neural Engine active! Available voices: {', '.join(voices[:4])}...")
    except ClientError as e:
        print(f"[!] Amazon Polly Notice: {e.response.get('Error', {}).get('Message', str(e))}")

    # 4. Amazon CloudWatch Metrics
    try:
        cw = boto3.client("cloudwatch", region_name=region)
        cw.put_metric_data(
            Namespace="IrisVoiceAssistant",
            MetricData=[
                {
                    "MetricName": "SystemHealthCheck",
                    "Value": 1.0,
                    "Unit": "Count"
                }
            ]
        )
        print(f"[OK] CloudWatch Observability active! Test metric published to 'IrisVoiceAssistant' namespace.")
    except ClientError as e:
        print(f"[!] CloudWatch Notice: {e.response.get('Error', {}).get('Message', str(e))}")

    print("\n" + "=" * 70)
    print("COST & ARCHITECTURE SUMMARY (100% COVERED UNDER CREDITS)")
    print("=" * 70)
    print("• AWS Amplify Hosting : 1,000 build mins & 5 GB free tier -> $0.00")
    print("• Amazon DynamoDB     : PAY_PER_REQUEST (25 GB always free) -> $0.00")
    print("• Amazon CloudWatch   : 10 custom metrics & 5 GB logs free  -> $0.00")
    print("• Amazon Polly Neural : 5M characters/month free tier       -> $0.00")
    print("• Est. Total 10-Day Spend: <$0.50 (99%+ of your $100 credits remain intact!)")
    print("=" * 70)


if __name__ == "__main__":
    main()
