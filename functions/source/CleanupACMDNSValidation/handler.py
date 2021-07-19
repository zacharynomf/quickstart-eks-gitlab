import json
import logging
import boto3
import cfnresponse
import time
import re


acm_client = boto3.client('acm')
r53_client = boto3.client('route53')
lambda_client = boto3.client('lambda')
logs_client = boto3.client('logs')


def handler(event, context):
    print('Received event: %s' % json.dumps(event))
    status = cfnresponse.SUCCESS
    physical_resource_id = None
    data = {}
    reason = None
    try:
        if event['RequestType'] == 'Create':
            token = ''.join(ch for ch in str(event['StackId'] + event['LogicalResourceId']) if ch.isalnum())
            token = token[len(token) - 32:]
            # Generated Physical ID doesn't do anything on create
            physical_resource_id = token
        elif event['RequestType'] == 'Update':
            # doesn't do anything on create
            physical_resource_id = event['PhysicalResourceId']
        elif event['RequestType'] == 'Delete':
            physical_resource_id = event['PhysicalResourceId']
            acm_arn = event["ResourceProperties"]["ACMArn"]
            rs = {}
            for d in acm_client.describe_certificate(CertificateArn=acm_arn)['Certificate']['DomainValidationOptions']:
                rs[d['ResourceRecord']['Name']] = d['ResourceRecord']['Value']
            rs = [{'Action': 'DELETE', 'ResourceRecordSet': {'Name': r, 'Type': 'CNAME', 'TTL': 600,'ResourceRecords': [{'Value': rs[r]}]}} for r in rs.keys()]
            try:
                r53_client.change_resource_record_sets(HostedZoneId=event['ResourceProperties']['HostedZoneId'], ChangeBatch={'Changes': rs})
            except r53_client.exceptions.InvalidChangeBatch as e:
                pass
            time.sleep(30)

    except Exception as e:
        logging.error('Exception: %s' % e, exc_info=True)
        reason = str(e)
        status = cfnresponse.FAILED
    finally:
        if event['RequestType'] == 'Delete':
            try:
                wait_message = 'waiting for events for request_id %s to propagate to cloudwatch...' % context.aws_request_id
                while not logs_client.filter_log_events(
                        logGroupName=context.log_group_name,
                        logStreamNames=[context.log_stream_name],
                        filterPattern='"%s"' % wait_message
                )['events']:
                    print(wait_message)
                    time.sleep(5)
            except Exception as e:
                logging.error('Exception: %s' % e, exc_info=True)
                time.sleep(120)
        cfnresponse.send(event, context, status, data, physical_resource_id, reason)
