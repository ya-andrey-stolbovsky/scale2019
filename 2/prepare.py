#! /usr/bin/env python3
# coding = utf-8

import subprocess
import os
import shutil
import json
import boto3

REPOSITORY_DIR = '~/lab'
LAB_DIR = REPOSITORY_DIR + '/2'
ARCHIVE_NAME = '~/lab.zip'
FUNCTION_ZIP_FILE_NAME = 'lab.zip'
SERVICE_ACCOUNT_NAME = 'ymq-serverless-demo'
BUCKET_NAME = 'github-bot-bucket-2'
FUNCTION_NAME = 'github-bot'
REPO_URL = 'https://github.com/ya-andrey-stolbovsky/scale2019'

def delete_directory(path):
    path = os.path.expanduser(path)
    if os.path.exists(path):
        shutil.rmtree(path)

def pull_repository():
    delete_directory(REPOSITORY_DIR)
    subprocess.run(['git', 'clone', REPO_URL, os.path.expanduser(REPOSITORY_DIR)])

def create_archive():
    archive_path = os.path.expanduser(ARCHIVE_NAME)
    if os.path.exists(archive_path):
        os.remove(archive_path)
    path = os.path.expanduser(LAB_DIR)
    shutil.make_archive(path, 'zip', root_dir=path)

def call_yc_with_json_format(args_list):
    args = list(args_list)
    args.append('--format')
    args.append('json')
    args.append('--profile')
    args.append('ymq')
    process = subprocess.run(args, capture_output=True)
    #print('Run {}\nstderr:\n{}\nstdout:{}'.format(args, process.stderr, process.stdout))
    if process.stdout:
        return json.loads(process.stdout)
    else:
        return {}

def delete_static_creds():
    lst = call_yc_with_json_format(['yc', 'iam', 'access-key', 'list', '--service-account-name', SERVICE_ACCOUNT_NAME])
    for acc in lst:
        call_yc_with_json_format(['yc', 'iam', 'access-key', 'delete', '--id', acc['id']])

def create_static_creds():
    creds = call_yc_with_json_format(['yc', 'iam', 'access-key', 'create', '--description', 'Demo access key', '--service-account-name', SERVICE_ACCOUNT_NAME])
    access_key_id = creds['access_key']['key_id']
    secret_access_key = creds['secret']
    return access_key_id, secret_access_key

def patch_config_with_keys(access_key_id, secret_access_key):
    path = os.path.join(os.path.expanduser(LAB_DIR), 'config')
    #print('Open config: {}'.format(path))
    conf = json.load(open(path, 'r'))
    conf['access_key_id'] = access_key_id
    conf['secret_access_key'] = secret_access_key
    json.dump(conf, open(path, 'w'), indent=4, sort_keys=True)

def list_serverless(what):
    lst_json = call_yc_with_json_format(['yc', 'serverless', what, 'list'])
    return lst_json

def delete_serverless(what, exceptions=None):
    lst = list_serverless(what)
    for obj in lst:
        if not exceptions or obj['name'] not in exceptions:
            call_yc_with_json_format(['yc', 'serverless', what, 'delete', '--id', obj['id']])

def aws_env(access_key_id, secret_access_key):
    env = dict(os.environ)
    env['AWS_ACCESS_KEY_ID'] = access_key_id
    env['AWS_SECRET_ACCESS_KEY'] = secret_access_key
    return env

def call_aws_with_json_format(args_list, endpoint_url, access_key_id, secret_access_key):
    args = list(args_list)
    args.append('--output')
    args.append('json')
    args.append('--endpoint-url')
    args.append(endpoint_url)
    #print('Run {}'.format(args))
    process = subprocess.run(args, capture_output=True, env=aws_env(access_key_id, secret_access_key))
    #print('stderr:\n{}\nstdout:{}'.format(process.stderr, process.stdout))
    if process.stdout:
        return json.loads(process.stdout)
    else:
        return {}

def call_aws_sqs_with_json_format(args_list, access_key_id, secret_access_key):
    return call_aws_with_json_format(args_list, 'https://message-queue.api.cloud.yandex.net', access_key_id, secret_access_key)

def call_aws_s3_with_json_format(args_list, access_key_id, secret_access_key):
    return call_aws_with_json_format(args_list, 'https://storage.yandexcloud.net', access_key_id, secret_access_key)

def make_ymq_client(access_key_id, secret_access_key):
    session = boto3.session.Session()
    return session.client(
        service_name='sqs',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        endpoint_url='https://message-queue.api.cloud.yandex.net',
        region_name='ru-central1'
    )

def delete_queues(access_key_id, secret_access_key):
    client = make_ymq_client(access_key_id, secret_access_key)
    queues_list = client.list_queues()
    #print('queues_list: {}'.format(queues_list))
    if queues_list:
        for queue in queues_list.get('QueueUrls', []):
            client.delete_queue(QueueUrl=queue)

def make_s3_client(access_key_id, secret_access_key):
    session = boto3.session.Session()
    return session.client(
        service_name='s3',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        endpoint_url='https://storage.yandexcloud.net',
        region_name='ru-central1'
    )

def delete_objects_from_bucket(bucket_name, access_key_id, secret_access_key):
    client = make_s3_client(access_key_id, secret_access_key)
    objects_list = client.list_objects(Bucket=bucket_name)
    #print('objects_list: {}'.format(objects_list))
    contents = objects_list.get('Contents', [])
    if contents:
        for obj in contents:
            client.delete_object(Bucket=bucket_name, Key=obj['Key'])

def upload_archive(access_key_id, secret_access_key):
    client = make_s3_client(access_key_id, secret_access_key)
    client.put_object(Body=open(os.path.expanduser(ARCHIVE_NAME), 'rb'), Bucket=BUCKET_NAME, Key=FUNCTION_ZIP_FILE_NAME)

def upload_new_function_version():
    resp = call_yc_with_json_format(
        [
            'yc', 'serverless', 'function', 'version', 'create',
            '--function-name', FUNCTION_NAME,
            '--runtime', 'python37',
            '--entrypoint', 'main.handler',
            '--memory', '128m',
            '--execution-timeout', '30s',
            '--package-bucket-name', BUCKET_NAME,
            '--package-object-name', 'lab.zip',
            '--description', 'Initial function version for demo'
        ]
    )
    #print('Function version resp: {}'.format(resp))

def make_function_public():
    call_yc_with_json_format(['yc', 'serverless', 'function', 'allow-unauthenticated-invoke', '--name', FUNCTION_NAME])

def main():
    pull_repository()

    delete_serverless('function', [FUNCTION_NAME])
    delete_serverless('trigger')

    delete_static_creds()
    access_key_id, secret_access_key = create_static_creds()
    patch_config_with_keys(access_key_id, secret_access_key)

    delete_queues(access_key_id, secret_access_key)
    delete_objects_from_bucket(BUCKET_NAME, access_key_id, secret_access_key)

    create_archive()
    upload_archive(access_key_id, secret_access_key)

    make_function_public()
    upload_new_function_version()

main()
