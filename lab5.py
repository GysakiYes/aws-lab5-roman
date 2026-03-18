import argparse
import os
import sys

import boto3
import pandas as pd
from botocore.exceptions import ClientError, WaiterError


def create_key_pair(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    try:
        response = ec2.create_key_pair(KeyName=args.key_name)
        private_key = response["KeyMaterial"]

        with open(args.pem_path, "w") as f:
            f.write(private_key)

        os.chmod(args.pem_path, 0o400)

        print(f"Ключову пару '{args.key_name}' створено.")
        print(f"PEM-файл збережено: {args.pem_path}")
        print("Права доступу встановлено: 400")

    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "InvalidKeyPair.Duplicate":
            print(f"ПОМИЛКА: ключова пара '{args.key_name}' вже існує в AWS.")
            print("Якщо PEM-файл у тебе локально відсутній, видали цей key pair в AWS Console і створи новий.")
        else:
            print(f"ПОМИЛКА AWS: {e}")


def create_instance(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    try:
        response = ec2.run_instances(
            ImageId=args.image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=args.instance_type,
            KeyName=args.key_name,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": "demo-lab5"}]
                }
            ]
        )

        instance_id = response["Instances"][0]["InstanceId"]
        print(f"Інстанс створено. Instance ID: {instance_id}")

        print("Очікування переходу інстансу в стан running...")
        ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])

        describe = ec2.describe_instances(InstanceIds=[instance_id])
        instance = describe["Reservations"][0]["Instances"][0]
        public_ip = instance.get("PublicIpAddress", "ще не призначено")
        print(f"Public IP: {public_ip}")

    except WaiterError as e:
        print(f"ПОМИЛКА очікування запуску інстансу: {e}")
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def get_public_ip(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    try:
        describe = ec2.describe_instances(InstanceIds=[args.instance_id])
        for reservation in describe["Reservations"]:
            for instance in reservation["Instances"]:
                print(f"Instance ID: {instance['InstanceId']}")
                print(f"Public IP: {instance.get('PublicIpAddress', 'немає')}")
                print(f"State: {instance['State']['Name']}")
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def list_instances(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    try:
        response = ec2.describe_instances(
            Filters=[
                {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
            ]
        )

        found = False
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                found = True
                print("-----")
                print(f"Instance ID: {instance['InstanceId']}")
                print(f"Type: {instance['InstanceType']}")
                print(f"State: {instance['State']['Name']}")
                print(f"Public IP: {instance.get('PublicIpAddress', 'немає')}")
                print(f"Private IP: {instance.get('PrivateIpAddress', 'немає')}")

        if not found:
            print("Інстанси не знайдено.")

    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def stop_instance(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    try:
        response = ec2.stop_instances(InstanceIds=[args.instance_id])
        print("Запит на зупинку відправлено.")
        print(response)

        print("Очікування переходу інстансу в стан stopped...")
        ec2.get_waiter("instance_stopped").wait(InstanceIds=[args.instance_id])
        print("Інстанс успішно зупинено.")

    except WaiterError as e:
        print(f"ПОМИЛКА очікування зупинки інстансу: {e}")
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def terminate_instance(args):
    ec2 = boto3.client("ec2", region_name=args.region)
    try:
        response = ec2.terminate_instances(InstanceIds=[args.instance_id])
        print("Запит на термінацію відправлено.")
        print(response)

        print("Очікування переходу інстансу в стан terminated...")
        ec2.get_waiter("instance_terminated").wait(InstanceIds=[args.instance_id])
        print("Інстанс успішно терміновано.")

    except WaiterError as e:
        print(f"ПОМИЛКА очікування термінації інстансу: {e}")
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def create_bucket(args):
    s3 = boto3.client("s3", region_name=args.region)
    try:
        if args.region == "us-east-1":
            response = s3.create_bucket(Bucket=args.bucket_name)
        else:
            response = s3.create_bucket(
                Bucket=args.bucket_name,
                CreateBucketConfiguration={"LocationConstraint": args.region}
            )
        print(f"Бакет '{args.bucket_name}' створено.")
        print(response)

    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ["BucketAlreadyExists", "BucketAlreadyOwnedByYou"]:
            print(f"ПОМИЛКА: бакет '{args.bucket_name}' вже існує або вже належить тобі.")
        else:
            print(f"ПОМИЛКА AWS: {e}")


def list_buckets(args):
    s3 = boto3.client("s3")
    try:
        response = s3.list_buckets()
        print("Список бакетів:")
        for bucket in response["Buckets"]:
            print(bucket["Name"])
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def upload_file(args):
    s3 = boto3.client("s3", region_name=args.region)
    try:
        s3.upload_file(args.file_path, args.bucket_name, args.key)
        print(f"Файл '{args.file_path}' завантажено в s3://{args.bucket_name}/{args.key}")
    except FileNotFoundError:
        print(f"ПОМИЛКА: локальний файл '{args.file_path}' не знайдено.")
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def read_csv(args):
    s3 = boto3.client("s3", region_name=args.region)
    try:
        obj = s3.get_object(Bucket=args.bucket_name, Key=args.key)
        data = pd.read_csv(obj["Body"])
        print("Перші 5 рядків датафрейму:")
        print(data.head())
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ["NoSuchKey", "404"]:
            print(f"ПОМИЛКА: файла '{args.key}' у бакеті '{args.bucket_name}' не існує.")
        elif code == "NoSuchBucket":
            print(f"ПОМИЛКА: бакета '{args.bucket_name}' не існує.")
        else:
            print(f"ПОМИЛКА AWS: {e}")


def delete_object(args):
    s3 = boto3.client("s3", region_name=args.region)
    try:
        s3.delete_object(Bucket=args.bucket_name, Key=args.key)
        print(f"Об'єкт '{args.key}' видалено з бакета '{args.bucket_name}'.")
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def delete_bucket(args):
    s3 = boto3.client("s3", region_name=args.region)
    try:
        response = s3.delete_bucket(Bucket=args.bucket_name)
        print(f"Бакет '{args.bucket_name}' видалено.")
        print(response)
    except ClientError as e:
        print(f"ПОМИЛКА AWS: {e}")


def build_parser():
    parser = argparse.ArgumentParser(description="ЛР5 - автоматизація AWS через boto3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("create-key")
    p.add_argument("--key-name", required=True)
    p.add_argument("--pem-path", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=create_key_pair)

    p = subparsers.add_parser("create-instance")
    p.add_argument("--image-id", required=True)
    p.add_argument("--instance-type", required=True)
    p.add_argument("--key-name", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=create_instance)

    p = subparsers.add_parser("get-ip")
    p.add_argument("--instance-id", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=get_public_ip)

    p = subparsers.add_parser("list-instances")
    p.add_argument("--region", required=True)
    p.set_defaults(func=list_instances)

    p = subparsers.add_parser("stop-instance")
    p.add_argument("--instance-id", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=stop_instance)

    p = subparsers.add_parser("terminate-instance")
    p.add_argument("--instance-id", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=terminate_instance)

    p = subparsers.add_parser("create-bucket")
    p.add_argument("--bucket-name", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=create_bucket)

    p = subparsers.add_parser("list-buckets")
    p.add_argument("--region", required=False, default="us-west-2")
    p.set_defaults(func=list_buckets)

    p = subparsers.add_parser("upload-file")
    p.add_argument("--bucket-name", required=True)
    p.add_argument("--file-path", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=upload_file)

    p = subparsers.add_parser("read-csv")
    p.add_argument("--bucket-name", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=read_csv)

    p = subparsers.add_parser("delete-object")
    p.add_argument("--bucket-name", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=delete_object)

    p = subparsers.add_parser("delete-bucket")
    p.add_argument("--bucket-name", required=True)
    p.add_argument("--region", required=True)
    p.set_defaults(func=delete_bucket)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
