# Script para fazer upload de vídeo e monitorar processamento
param(
    [Parameter(Mandatory=$true)]
    [string]$VideoPath,
    
    [Parameter(Mandatory=$false)]
    [string]$BucketName = "fiapx-video-input-637423242759-20260131211044",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

Write-Host "🎬 Testando processamento de vídeo" -ForegroundColor Green
Write-Host ""

# Verificar se o arquivo existe
if (-not (Test-Path $VideoPath)) {
    Write-Host "❌ Erro: Arquivo não encontrado: $VideoPath" -ForegroundColor Red
    exit 1
}

# Obter nome do arquivo
$fileName = Split-Path $VideoPath -Leaf
$s3Key = "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$fileName"

Write-Host "📤 Fazendo upload do vídeo..." -ForegroundColor Yellow
Write-Host "   Arquivo: $VideoPath"
Write-Host "   Destino: s3://$BucketName/$s3Key"
Write-Host ""

# Upload do vídeo
aws s3 cp $VideoPath "s3://$BucketName/$s3Key" --region $Region

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Upload concluído!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 Monitorando processamento..." -ForegroundColor Cyan
    Write-Host "   Aguarde alguns segundos para a Lambda 1 processar..." -ForegroundColor Yellow
    Write-Host ""
    
    # Aguardar um pouco antes de verificar
    Start-Sleep -Seconds 5
    
    Write-Host "🔍 Verificando logs da Lambda 1..." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Para ver logs em tempo real, execute:" -ForegroundColor Yellow
    Write-Host "  aws logs tail /aws/lambda/video-frame-extraction --follow --region $Region" -ForegroundColor White
    Write-Host ""
    Write-Host "Para verificar frames extraídos:" -ForegroundColor Yellow
    Write-Host "  aws s3 ls s3://fiapx-video-output-637423242759-20260131211044/frames/ --recursive --region $Region" -ForegroundColor White
    Write-Host ""
    Write-Host "Para verificar ZIP criado:" -ForegroundColor Yellow
    Write-Host "  aws s3 ls s3://fiapx-video-output-637423242759-20260131211044/zips/ --recursive --region $Region" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Erro no upload!" -ForegroundColor Red
    exit 1
}
