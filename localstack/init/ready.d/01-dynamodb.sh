#!/bin/bash
awslocal dynamodb create-table \
  --table-name lomax-productos-atributos \
  --attribute-definitions AttributeName=producto_id,AttributeType=N \
  --key-schema AttributeName=producto_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST 2>/dev/null || echo "Tabla ya existe"