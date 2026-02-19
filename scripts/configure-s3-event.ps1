# Script para configurar evento S3 que aciona a Lambda 1
# Execute este script após fazer o deploy do SAM

param(
    [Parameter(Mandatory=$true)]
    [string]$InputBucketName,
    
    [Parameter(Mandatory=$true)]
    [string]$LambdaFunctionName = "video-frame-extraction",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

Write-Host "Configurando evento S3 para acionar Lambda..." -ForegroundColor Green

# 1. Obter ARN da Lambda
Write-Host "Obtendo ARN da Lambda: $LambdaFunctionName" -ForegroundColor Yellow
$lambdaArn = aws lambda get-function --function-name $LambdaFunctionName --region $Region --query 'Configuration.FunctionArn' --output text

if (-not $lambdaArn) {
    Write-Host "Erro: Lambda function não encontrada!" -ForegroundColor Red
    exit 1
}

Write-Host "ARN da Lambda: $lambdaArn" -ForegroundColor Cyan

# 2. Adicionar permissão para S3 invocar a Lambda
Write-Host "Adicionando permissão para S3 invocar Lambda..." -ForegroundColor Yellow
$sourceArn = "arn:aws:s3:::$InputBucketName"

try {
    aws lambda add-permission `
        --function-name $LambdaFunctionName `
        --principal s3.amazonaws.com `
        --statement-id "s3-trigger-$InputBucketName" `
        --action "lambda:InvokeFunction" `
        --source-arn $sourceArn `
        --region $Region `
        --output json | Out-Null
    
    Write-Host "Permissão adicionada com sucesso!" -ForegroundColor Green
} catch {
    Write-Host "Aviso: Permissão pode já existir. Continuando..." -ForegroundColor Yellow
}

# 3. Criar configuração de notificação S3
Write-Host "Criando configuração de notificação S3..." -ForegroundColor Yellow

$notificationConfig = @{
    LambdaFunctionConfigurations = @(
        @{
            LambdaFunctionArn = $lambdaArn
            Events = @("s3:ObjectCreated:*")
            Filter = @{
                Key = @{
                    FilterRules = @(
                        @{
                            Name = "suffix"
                            Value = ".mp4"
                        },
                        @{
                            Name = "suffix"
                            Value = ".avi"
                        },
                        @{
                            Name = "suffix"
                            Value = ".mov"
                        },
                        @{
                            Name = "suffix"
                            Value = ".mkv"
                        }
                    )
                }
            }
        }
    )
} | ConvertTo-Json -Depth 10

$tempFile = [System.IO.Path]::GetTempFileName()
$notificationConfig | Out-File -FilePath $tempFile -Encoding utf8

# 4. Aplicar configuração de notificação
Write-Host "Aplicando configuração de notificação no bucket S3..." -ForegroundColor Yellow

try {
    aws s3api put-bucket-notification-configuration `
        --bucket $InputBucketName `
        --notification-configuration "file://$tempFile" `
        --region $Region `
        --output json | Out-Null
    
    Write-Host "Configuração aplicada com sucesso!" -ForegroundColor Green
} catch {
    Write-Host "Erro ao aplicar configuração: $_" -ForegroundColor Red
    Remove-Item $tempFile -ErrorAction SilentlyContinue
    exit 1
}

# Limpar arquivo temporário
Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Host "`n✅ Configuração concluída!" -ForegroundColor Green
Write-Host "A Lambda será acionada quando vídeos forem enviados para: s3://$InputBucketName/" -ForegroundColor Cyan
