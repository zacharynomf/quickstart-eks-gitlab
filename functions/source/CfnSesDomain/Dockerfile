FROM public.ecr.aws/sam/build-python3.9:latest

COPY aws-cfn-ses-domain ./

RUN zip -X -r lambda.zip ./aws_cfn_ses_domain/ index.py

CMD mkdir -p /output/ && mv lambda.zip /output/
