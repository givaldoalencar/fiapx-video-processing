#!/bin/bash
# Script para configurar evento S3 que aciona a Lambda 1
# Execute este script após fazer o deploy do SAM

set -e

# Parâmetros
INPUT_BUCKET_NAME="${1}"
LAMBDA_FUNCTION_NAME="${2:-video-frame-extraction}"
REGION="${3:-us-east-1}"

if [ -z "$INPUT_BUCKET_NAME" ]; then
    echo "Erro: Nome do bucket é obrigatório"
    echo "Uso: $0 <bucket-name> [lambda-function-name] [region]"
    exit 1
fi

echo "🔧 Configurando evento S3 para acionar Lambda..."

# 1. Obter ARN da Lambda
echo "📋 Obtendo ARN da Lambda: $LAMBDA_FUNCTION_NAME"
LAMBDA_ARN=$(aws lambda get-function \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)

if [ -z "$LAMBDA_ARN" ]; then
    echo "❌ Erro: Lambda function não encontrada!"
    exit 1
fi

echo "✅ ARN da Lambda: $LAMBDA_ARN"

# 2. Adicionar permissão para S3 invocar a Lambda
echo "🔐 Adicionando permissão para S3 invocar Lambda..."
SOURCE_ARN="arn:aws:s3:::$INPUT_BUCKET_NAME"

aws lambda add-permission \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --principal s3.amazonaws.com \
    --statement-id "s3-trigger-$INPUT_BUCKET_NAME" \
    --action "lambda:InvokeFunction" \
    --source-arn "$SOURCE_ARN" \
    --region "$REGION" \
    2>/dev/null || echo "⚠️  Aviso: Permissão pode já existir. Continuando..."

# 3. Criar configuração de notificação S3
echo "📝 Criando configuração de notificação S3..."

NOTIFICATION_CONFIG=$(cat <<EOF
{
    "LambdaFunctionConfigurations": [
        {
            "LambdaFunctionArn": "$LAMBDA_ARN",
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "suffix",
                            "Value": ".mp4"
                        },
                        {
                            "Name": "suffix",
                            "Value": ".avi"
                        },
                        {
                            "Name": "suffix",
                            "Value": ".mov"
                        },
                        {
                            "Name": "suffix",
                            "Value": ".mkv"
                        }
                    ]
                }
            }
        }
    ]
}
EOF
)

# 4. Aplicar configuração de notificação
echo "🚀 Aplicando configuração de notificação no bucket S3..."

echo "$NOTIFICATION_CONFIG" | aws s3api put-bucket-notification-configuration \
    --bucket "$INPUT_BUCKET_NAME" \
    --notification-configuration file:///dev/stdin \
    --region "$REGION"

echo ""
echo "✅ Configuração concluída!"
echo "📦 A Lambda será acionada quando vídeos forem enviados para: s3://$INPUT_BUCKET_NAME/"
