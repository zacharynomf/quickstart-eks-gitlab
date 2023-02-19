import boto3
import cfnresponse
import json
import logging

acm_client = boto3.client("acm")
r53_client = boto3.client("route53")

def handler(event, context):
    print('Received event: %s' % json.dumps(event))
    status = cfnresponse.SUCCESS
    physical_resource_id = None
    data = {}
    reason = None

    try:
        if event["RequestType"] == "Create":
            token = "".join(
                ch
                for ch in str(event["StackId"] + event["LogicalResourceId"])
                if ch.isalnum()
            )
            token = token[len(token) - 32 :]
            # Generated Physical ID doesn't do anything on create
            physical_resource_id = token
        elif event["RequestType"] == "Update":
            # doesn't do anything on create
            physical_resource_id = event["PhysicalResourceId"]
        elif event["RequestType"] == "Delete":
            acm_arn = event["ResourceProperties"]["ACMArn"]
            hosted_zone_id = event["ResourceProperties"]["HostedZoneId"]
            physical_resource_id = event["PhysicalResourceId"]

            changes = []
            certificate = acm_client.describe_certificate(CertificateArn=acm_arn)
            for d in certificate["Certificate"]["DomainValidationOptions"]:
                record_name = d["ResourceRecord"]["Name"]
                record_type = d["ResourceRecord"]["Type"]

                # Retreiving information about the record (we need TTL in particular)
                response = r53_client.list_resource_record_sets(
                    HostedZoneId=hosted_zone_id,
                    StartRecordName=record_name,
                    StartRecordType=record_type,
                )

                record = next(
                    filter(
                        lambda x: x["Name"] == record_name,
                        response["ResourceRecordSets"],
                    )
                )

                changes.append(
                    {
                        "Action": "DELETE",
                        "ResourceRecordSet": {
                            "Name": record_name,
                            "Type": record_type,
                            "TTL": record["TTL"],
                            "ResourceRecords": record["ResourceRecords"],
                        },
                    }
                )

            r53_client.change_resource_record_sets(
                HostedZoneId=hosted_zone_id, ChangeBatch={"Changes": changes}
            )

    except Exception as e:
        logging.error('Exception: %s' % e, exc_info=True)
        reason = str(e)
        status = cfnresponse.FAILED
    finally:
        cfnresponse.send(event, context, status, data, physical_resource_id, reason)
