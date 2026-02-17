# Script para monitorar o processamento em tempo real
param(
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

Write-Host "📊 Monitorando processamento de vídeos" -ForegroundColor Green
Write-Host ""

# Verificar logs da Lambda 1
Write-Host "🔍 Lambda 1 - Frame Extraction (últimas 20 linhas):" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray
aws logs tail /aws/lambda/video-frame-extraction --since 10m --region $Region --format short | Select-Object -Last 20
Write-Host ""

# Verificar logs da Lambda 2 (se existir)
Write-Host "🔍 Lambda 2 - ZIP Compression (últimas 20 linhas):" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray
try {
    aws logs tail /aws/lambda/video-zip-compression --since 10m --region $Region --format short | Select-Object -Last 20
} catch {
    Write-Host "   (Nenhum log ainda - Lambda 2 ainda não foi executada)" -ForegroundColor Yellow
}
Write-Host ""

# Verificar DLQs
Write-Host "📬 Dead Letter Queues:" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray
$dlq1 = aws sqs get-queue-attributes --queue-url https://sqs.$Region.amazonaws.com/637423242759/video-frame-extraction-dlq --attribute-names ApproximateNumberOfMessages --region $Region --query 'Attributes.ApproximateNumberOfMessages' --output text
$dlq2 = aws sqs get-queue-attributes --queue-url https://sqs.$Region.amazonaws.com/637423242759/video-zip-compression-dlq --attribute-names ApproximateNumberOfMessages --region $Region --query 'Attributes.ApproximateNumberOfMessages' --output text

Write-Host "   FrameExtractionDLQ: $dlq1 mensagens" -ForegroundColor $(if ($dlq1 -eq "0") { "Green" } else { "Red" })
Write-Host "   ZipCompressionDLQ: $dlq2 mensagens" -ForegroundColor $(if ($dlq2 -eq "0") { "Green" } else { "Red" })
Write-Host ""

# Verificar resultados no S3
Write-Host "📦 Resultados no S3:" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Gray

Write-Host "   Frames extraídos (últimos 5):" -ForegroundColor Yellow
aws s3 ls s3://fiapx-video-output-637423242759-20260131211044/frames/ --recursive --region $Region | Select-Object -Last 5 | ForEach-Object { Write-Host "     $_" -ForegroundColor White }

Write-Host ""
Write-Host "   ZIPs criados:" -ForegroundColor Yellow
$zips = aws s3 ls s3://fiapx-video-output-637423242759-20260131211044/zips/ --recursive --region $Region
if ($zips) {
    $zips | ForEach-Object { Write-Host "     $_" -ForegroundColor White }
} else {
    Write-Host "     (Nenhum ZIP encontrado ainda)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "Para monitorar em tempo real:" -ForegroundColor Cyan
Write-Host "   aws logs tail /aws/lambda/video-frame-extraction --follow --region $Region" -ForegroundColor White
Write-Host "   aws logs tail /aws/lambda/video-zip-compression --follow --region $Region" -ForegroundColor White
