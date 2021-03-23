import os, json, boto3, traceback
ec2 = boto3.client('ec2')
route53 = boto3.client('route53')
autoscaling = boto3.client('autoscaling')

HOSTED_ZONE_ID = os.environ['HOSTED_ZONE_ID']
HOSTED_ZONE_NAME = os.environ['HOSTED_ZONE_NAME']
REPLICA_TAG_NAME = os.environ['REPLICA_TAG_NAME']
MAX_REPLICAS = int(os.environ['MAX_REPLICAS'])
ALL_REPLICAS = { str(r) for r in range(0, MAX_REPLICAS) }

LAUNCHING_TRANSITION = 'autoscaling:EC2_INSTANCE_LAUNCHING'
TERMINATING_TRANSITION = 'autoscaling:EC2_INSTANCE_TERMINATING'

def get_instance_ip_address(instance):
  return instance['PrivateIpAddress']

def get_replica_number(instance):
  tags = instance['Tags']
  return next(str(t['Value']) for t in tags if t['Key'] == REPLICA_TAG_NAME)

def update_replica_number(instance_id, replica_number, transition):
  if transition == LAUNCHING_TRANSITION:
    response = ec2.create_tags(
      Resources=[ instance_id ],
      Tags=[ { 'Key': REPLICA_TAG_NAME, 'Value': replica_number } ]
    )

def get_instance_by_id(instance_id):
  response = ec2.describe_instances(
    InstanceIds=[ instance_id ]
  )
  reservations = response['Reservations']
  instances = [ instance for r in reservations for instance in r['Instances'] ]
  return next(iter(instances))

def get_free_replica_number():
  response = ec2.describe_instances(
    Filters=[
      { 'Name': 'instance-state-name', 'Values': [ 'running' ] },
      { 'Name': 'tag-key', 'Values': [ REPLICA_TAG_NAME ] }
    ]
  )

  reservations = response['Reservations']
  running_replicas = { get_replica_number(instance) for r in reservations for instance in r['Instances'] }
  print(f'running replicas: {running_replicas}')
  free_replicas =  ALL_REPLICAS.difference(running_replicas)
  print(f'free replicas: {free_replicas}')

  return next(iter(free_replicas))

def get_replica_number_for_transition(instance, transition):
  if transition == LAUNCHING_TRANSITION:
    return get_free_replica_number()
  
  if transition == TERMINATING_TRANSITION:
    return get_replica_number(instance)
  
  raise RuntimeError(f'Unsupported transition: {transition}')

def update_dns_record(transition, replica_hostname, instance_ip):
  action = 'UPSERT' if transition == LAUNCHING_TRANSITION else 'DELETE'
  response = route53.change_resource_record_sets(
    HostedZoneId=HOSTED_ZONE_ID,
    ChangeBatch={
      'Changes': [
        {
          'Action': action,
          'ResourceRecordSet': {
            'Name': f'{replica_hostname}.{HOSTED_ZONE_NAME}',
            'Type': 'A',
            'TTL': 60,
            'ResourceRecords': [ { 'Value': instance_ip } ]
          }
        }
      ]
    }
  )
  print('successfully updated dns')

def check_response(response_json):
  try:
    if response_json['ResponseMetadata']['HTTPStatusCode'] == 200:
      return True
    else:
      return False
  except KeyError:
    return False

def create_replica_host_name(slot):
  return f'gitaly-{slot}'

def continue_lifecycle_hook(instance_id, event):
  complete_lifecycle_hook(instance_id, event, 'CONTINUE')

def abandon_lifecycle_hook(instance_id, event):
  complete_lifecycle_hook(instance_id, event, 'ABANDON')

def complete_lifecycle_hook(instance_id, event, action_result):
  try:
    response = autoscaling.complete_lifecycle_action(
      LifecycleHookName=event['LifecycleHookName'],
      AutoScalingGroupName=event['AutoScalingGroupName'],
      LifecycleActionResult=action_result,
      InstanceId=instance_id
    )
    if check_response(response):
      print(f"Lifecycle hook completed correctly: {response}")
    else:
      print(f"Lifecycle hook could not be completed: {response}")
  except:
      print(f"Lifecycle hook completion could not be executed: {traceback.format_exc()}")
      return None    

def lambda_handler(event, context):
  for record in event['Records']:
    payload = record['body']
    print(f'Received message: {payload}')
    request = json.loads(payload)              
    transition = request.get('LifecycleTransition', '')

    if transition in [ LAUNCHING_TRANSITION, TERMINATING_TRANSITION ]:
      instance_id = request['EC2InstanceId'] 

      try:                
        instance = get_instance_by_id(instance_id)
        instance_ip = get_instance_ip_address(instance)
        slot = get_replica_number_for_transition(instance, transition)       
        replica_hostname = create_replica_host_name(slot)

        print(f'updating DNS for {replica_hostname} = {instance_ip}')
        update_dns_record(transition, replica_hostname, instance_ip)
        update_replica_number(instance_id, slot, transition)

        continue_lifecycle_hook(instance_id, request)
      except Exception:
        print(traceback.format_exc())
        abandon_lifecycle_hook(instance_id, request)