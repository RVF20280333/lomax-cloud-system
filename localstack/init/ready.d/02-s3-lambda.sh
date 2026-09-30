#!/bin/bash
awslocal s3 mb s3://lomax-originales 2>/dev/null
awslocal s3 mb s3://lomax-miniaturas 2>/dev/null

if [ -f /lambda/function.zip ]; then
  awslocal lambda delete-function --function-name lomax-resizer 2>/dev/null
  awslocal lambda create-function \
    --function-name lomax-resizer \
    --runtime python3.11 \
    --handler lambda_function.lambda_handler \
    --zip-file fileb:///lambda/function.zip \
    --timeout 30 \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --environment "Variables={AWS_ENDPOINT_URL=http://localstack:4566}"
else
  echo "No se encontró /lambda/function.zip"
fi