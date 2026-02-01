# 🚀 Guia de Deploy - FIApx Video Processing

Este documento fornece um guia passo a passo para fazer deploy do sistema de processamento de vídeo.

## 📋 Pré-requisitos

Antes de começar, certifique-se de ter:

- ✅ AWS CLI configurado e autenticado
- ✅ AWS SAM CLI instalado
- ✅ Python 3.11 instalado
- ✅ Dois buckets S3 criados (input e output)
- ✅ Permissões adequadas na AWS (IAM)

## 🔧 Passo 1: Preparar o Ambiente

### 1.1 Clonar o Repositório

```bash
git clone https://github.com/givaldoalencar/fiapx-video-processing.git
cd fiapx-video-processing
```

### 1.2 Instalar Dependências de Desenvolvimento

```bash
pip install -r requirements-dev.txt
pip install opencv-python-headless numpy
```

### 1.3 Executar Testes

```bash
pytest -v
```

Certifique-se de que todos os testes passam antes de fazer deploy.

## 📦 Passo 2: Configurar Buckets S3

### 2.1 Criar Buckets

```bash
# Bucket de entrada (para upload de vídeos)
aws s3 mb s3://fiapx-video-input-SEU-ID --region us-east-1

# Bucket de saída (para frames e ZIPs)
aws s3 mb s3://fiapx-video-output-SEU-ID --region us-east-1
```

### 2.2 Atualizar samconfig.toml

Edite o arquivo `samconfig.toml` e atualize os parâmetros:

```toml
parameter_overrides = [
    "InputBucket=fiapx-video-input-SEU-ID",
    "OutputBucket=fiapx-video-output-SEU-ID",
    "FramesPerSecond=1.0"
]
```

## 🔨 Passo 3: Build e Deploy

### 3.1 Build

**Windows:**
```powershell
sam build
```

**Linux/macOS:**
```bash
sam build
```

### 3.2 Deploy

**Windows:**
```powershell
sam deploy --no-confirm-changeset
```

**Linux/macOS:**
```bash
sam deploy
```

O deploy criará:
- ✅ Lambda 1 (video-frame-extraction)
- ✅ Lambda 2 (video-zip-compression)
- ✅ SNS Topic (video-processing-notifications)
- ✅ Dead Letter Queues (2 filas SQS)

## ⚙️ Passo 4: Configurar Evento S3

Após o deploy, configure o evento S3 para acionar a Lambda 1:

### 4.1 Usando Script (Recomendado)

**Windows:**
```powershell
.\scripts\configure-s3-event.ps1 -InputBucketName "fiapx-video-input-SEU-ID"
```

**Linux/macOS:**
```bash
chmod +x scripts/configure-s3-event.sh
./scripts/configure-s3-event.sh "fiapx-video-input-SEU-ID"
```

### 4.2 Verificar Configuração

```bash
aws s3api get-bucket-notification-configuration --bucket fiapx-video-input-SEU-ID
```

## ✅ Passo 5: Verificar Deploy

### 5.1 Verificar Stack

```bash
aws cloudformation describe-stacks --stack-name fiapx-video-processing
```

### 5.2 Verificar Lambdas

```bash
aws lambda list-functions --query "Functions[?contains(FunctionName, 'video')]"
```

### 5.3 Verificar SNS Topic

```bash
aws sns list-topics --query "Topics[?contains(TopicArn, 'video-processing')]"
```

### 5.4 Verificar DLQs

```bash
aws sqs list-queues --queue-name-prefix video
```

## 🧪 Passo 6: Testar o Sistema

### 6.1 Upload de Vídeo de Teste

```bash
aws s3 cp seu-video.mp4 s3://fiapx-video-input-SEU-ID/
```

### 6.2 Monitorar Processamento

**Ver logs da Lambda 1:**
```bash
aws logs tail /aws/lambda/video-frame-extraction --follow
```

**Ver logs da Lambda 2:**
```bash
aws logs tail /aws/lambda/video-zip-compression --follow
```

### 6.3 Verificar Resultados

```bash
# Verificar frames extraídos
aws s3 ls s3://fiapx-video-output-SEU-ID/frames/ --recursive

# Verificar ZIP criado
aws s3 ls s3://fiapx-video-output-SEU-ID/zips/
```

## 📊 Passo 7: Configurar Monitoramento (Opcional)

### 7.1 Configurar Notificação por Email

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT:video-processing-notifications \
  --protocol email \
  --notification-endpoint seu-email@exemplo.com
```

Confirme a assinatura no email recebido.

### 7.2 Configurar CloudWatch Alarms

Crie alarmes para monitorar:
- Erros nas lambdas
- Mensagens na DLQ
- Tempo de execução

## 🔄 Atualizações Futuras

Para atualizar o sistema:

1. Faça as alterações no código
2. Execute os testes: `pytest -v`
3. Faça build: `sam build`
4. Faça deploy: `sam deploy --no-confirm-changeset`

## 🗑️ Remover Recursos

Para remover todos os recursos criados:

```bash
sam delete
```

**⚠️ Atenção:** Isso removerá todos os recursos, incluindo lambdas, SNS, DLQs, mas NÃO os buckets S3.

## ❓ Troubleshooting

### Erro: "Bucket already exists"
- Use um nome único para seus buckets
- Os nomes de buckets S3 devem ser globalmente únicos

### Erro: "Access Denied"
- Verifique suas credenciais AWS: `aws sts get-caller-identity`
- Verifique as permissões IAM

### Erro: "Function not found"
- Verifique se o deploy foi concluído com sucesso
- Verifique o nome da função no template.yaml

### Lambda não é acionada
- Verifique se o evento S3 foi configurado corretamente
- Execute o script de configuração novamente
- Verifique os logs do CloudWatch

## 📞 Suporte

Para mais informações, consulte:
- [README.md](README.md) - Documentação principal
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
