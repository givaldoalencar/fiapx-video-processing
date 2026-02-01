# FIApx Video Processing

Sistema de processamento de vídeo desenvolvido com arquitetura de microsserviços utilizando AWS Lambda.

## 📋 Descrição

Este projeto implementa um pipeline de processamento de vídeo que:
1. **Lambda 1**: Processa vídeos enviados ao S3, extraindo frames a intervalos regulares
2. **Lambda 2**: Compacta os frames extraídos em um arquivo ZIP

## 🏗️ Arquitetura

```
S3 (Upload) → Lambda 1 (Frame Extraction) → SNS → Lambda 2 (ZIP Compression) → S3 (Output)
```

### Componentes

- **Lambda 1 - Frame Extraction**: 
  - Trigger: Evento S3 (quando vídeo é enviado)
  - Função: Extrai frames do vídeo usando OpenCV
  - Saída: Frames salvos em bucket S3
  - Features: Processamento de múltiplos eventos, validação de formatos, logging estruturado
  - Dead Letter Queue: Para tratamento de falhas
  
- **Lambda 2 - ZIP Compression**:
  - Trigger: Notificação SNS (quando Lambda 1 completa)
  - Função: Baixa frames e compacta em ZIP
  - Saída: Arquivo ZIP no bucket S3
  - Features: Processamento de múltiplas mensagens, logging estruturado
  - Dead Letter Queue: Para tratamento de falhas

- **SNS Topic**: Gerencia notificações entre as lambdas
- **Dead Letter Queues (DLQ)**: Filas SQS para mensagens que falham (retenção de 14 dias)

## 🚀 Pré-requisitos

- AWS CLI configurado
- AWS SAM CLI instalado
- Python 3.11
- Conta AWS com permissões adequadas

## 📦 Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/givaldoalencar/fiapx-video-processing.git
cd fiapx-video-processing
```

### 2. Instalar dependências

```bash
# Instalar AWS SAM CLI (se ainda não tiver)
# macOS
brew install aws-sam-cli

# Linux
wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip
unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
sudo ./sam-installation/install

# Windows
# Baixar e instalar do site oficial: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
```

### 3. Configurar buckets S3

Crie dois buckets S3:
- Bucket de entrada (para upload de vídeos)
- Bucket de saída (para frames e ZIPs)

Atualize os parâmetros no arquivo `samconfig.toml`:

```toml
parameter_overrides = [
    "InputBucket=seu-bucket-entrada",
    "OutputBucket=seu-bucket-saida",
    "FramesPerSecond=1.0"
]
```

## 🔨 Build e Deploy

### Build

**Windows (Python 3.11):**
```powershell
# Adicionar Python 3.11 ao PATH temporariamente
$env:Path = "C:\Users\Caroline\AppData\Local\Programs\Python\Python311;C:\Users\Caroline\AppData\Local\Programs\Python\Python311\Scripts;" + $env:Path

# Build
C:\Users\Caroline\AppData\Local\Programs\Python\Python311\Scripts\sam.exe build
```

**Linux/macOS:**
```bash
sam build
```

### Deploy

**Windows:**
```powershell
C:\Users\Caroline\AppData\Local\Programs\Python\Python311\Scripts\sam.exe deploy --no-confirm-changeset
```

**Linux/macOS:**
```bash
sam deploy
```

### Configurar Evento S3

Após o deploy, configure o evento S3 para acionar a Lambda 1 quando um vídeo for enviado:

**Windows (PowerShell):**
```powershell
.\scripts\configure-s3-event.ps1 -InputBucketName "fiapx-video-input-637423242759-20260131211044"
```

**Linux/macOS (Bash):**
```bash
chmod +x scripts/configure-s3-event.sh
./scripts/configure-s3-event.sh "fiapx-video-input-637423242759-20260131211044"
```

**Ou manualmente via AWS CLI:**
```powershell
# Adicionar permissão
aws lambda add-permission --function-name video-frame-extraction --principal s3.amazonaws.com --statement-id s3-trigger --action "lambda:InvokeFunction" --source-arn "arn:aws:s3:::seu-bucket-entrada" --region us-east-1

# Configurar notificação (usar o script é mais fácil)
```

## ✅ Status do Deploy

**Deploy concluído com sucesso!**

- **Stack**: `fiapx-video-processing`
- **Região**: `us-east-1`
- **Lambda 1**: `video-frame-extraction` ✅
- **Lambda 2**: `video-zip-compression` ✅
- **SNS Topic**: `video-processing-notifications` ✅
- **Evento S3**: Configurado ✅

**Buckets S3:**
- Input: `fiapx-video-input-637423242759-20260131211044`
- Output: `fiapx-video-output-637423242759-20260131211044`

## 📝 Estrutura do Projeto

```
fiapx-video-processing/
├── lambda1_frame_extraction/
│   ├── handler.py              # Código principal Lambda 1
│   └── requirements.txt        # Dependências Lambda 1
├── lambda2_zip_compression/
│   ├── handler.py              # Código principal Lambda 2
│   └── requirements.txt        # Dependências Lambda 2
├── tests/
│   ├── test_lambda1_frame_extraction.py
│   └── test_lambda2_zip_compression.py
├── scripts/
│   ├── configure-s3-event.ps1  # Script Windows para configurar S3
│   └── configure-s3-event.sh   # Script Linux/macOS para configurar S3
├── events/
│   ├── s3-event-example.json   # Exemplo de evento S3 para testes locais
│   └── sns-event-example.json  # Exemplo de evento SNS para testes locais
├── template.yaml                # SAM template
├── samconfig.toml              # Configuração SAM
├── pytest.ini                  # Configuração pytest
├── requirements-dev.txt        # Dependências de desenvolvimento
└── README.md                   # Este arquivo
```

## ⚙️ Configuração

### Variáveis de Ambiente

**Lambda 1:**
- `OUTPUT_BUCKET`: Bucket para salvar frames
- `FRAMES_PER_SECOND`: Frames por segundo a extrair (padrão: 1.0)
- `SNS_TOPIC_ARN`: ARN do tópico SNS (configurado automaticamente)

**Lambda 2:**
- `INPUT_BUCKET`: Bucket de onde ler os frames
- `OUTPUT_BUCKET`: Bucket para salvar o ZIP
- `SNS_TOPIC_ARN`: ARN do tópico SNS (configurado automaticamente)

## 🔄 Fluxo de Processamento

1. **Upload de Vídeo**: Vídeo é enviado para o bucket de entrada
2. **Trigger Lambda 1**: Evento S3 dispara a Lambda 1
3. **Extração de Frames**: Lambda 1 processa o vídeo e extrai frames
4. **Upload de Frames**: Frames são salvos no bucket de saída
5. **Notificação SNS**: Lambda 1 publica mensagem no SNS
6. **Trigger Lambda 2**: SNS dispara a Lambda 2
7. **Download de Frames**: Lambda 2 baixa os frames do bucket
8. **Compactação**: Frames são compactados em ZIP
9. **Upload de ZIP**: Arquivo ZIP é salvo no bucket de saída

## 📊 Monitoramento

As lambdas publicam notificações no SNS quando:
- Processamento é concluído com sucesso
- Ocorre um erro no processamento

Configure um subscriber SNS (email, SQS, etc.) para receber notificações.

## 🧪 Testes

### Executar Testes

```bash
# Instalar dependências de desenvolvimento
pip install -r requirements-dev.txt
pip install opencv-python-headless numpy

# Executar todos os testes
pytest -v

# Executar com cobertura
pytest --cov

# Executar testes específicos
pytest tests/test_lambda1_frame_extraction.py -v
```

### Cobertura de Testes

- **Lambda 1**: 84% de cobertura
- **Lambda 2**: 83% de cobertura
- **Total**: 84% de cobertura

## 🛠️ Desenvolvimento

### Adicionar novas funcionalidades

1. Modifique o código da lambda correspondente
2. Atualize os testes
3. Execute os testes: `pytest -v`
4. Faça build: `sam build`
5. Deploy: `sam deploy`

### Debug local

```bash
# Testar Lambda 1 localmente
sam local invoke FrameExtractionFunction --event events/s3-event-example.json --debug

# Testar Lambda 2 localmente
sam local invoke ZipCompressionFunction --event events/sns-event-example.json --debug
```

## 📊 Monitoramento e Observabilidade

### Dead Letter Queues (DLQ)

Ambas as lambdas possuem Dead Letter Queues configuradas:
- **FrameExtractionDLQ**: Para falhas na Lambda 1
- **ZipCompressionDLQ**: Para falhas na Lambda 2
- Retenção: 14 dias para análise de erros

### Logs

As lambdas utilizam logging estruturado com níveis apropriados:
- **INFO**: Operações normais e progresso
- **ERROR**: Erros e exceções
- **WARNING**: Avisos e situações não críticas

Visualize os logs no CloudWatch:
```bash
aws logs tail /aws/lambda/video-frame-extraction --follow
aws logs tail /aws/lambda/video-zip-compression --follow
```

### Notificações SNS

As lambdas publicam notificações no SNS quando:
- Processamento é concluído com sucesso
- Ocorre um erro no processamento

Configure um subscriber SNS (email, SQS, etc.) para receber notificações:
```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT:video-processing-notifications \
  --protocol email \
  --notification-endpoint seu-email@exemplo.com
```

## ⚠️ Troubleshooting

### Problema: Lambda não é acionada pelo S3

1. Verifique se o evento S3 foi configurado:
   ```bash
   aws s3api get-bucket-notification-configuration --bucket seu-bucket-entrada
   ```

2. Verifique as permissões da Lambda:
   ```bash
   aws lambda get-policy --function-name video-frame-extraction
   ```

3. Execute o script de configuração novamente:
   ```powershell
   .\scripts\configure-s3-event.ps1 -InputBucketName "seu-bucket"
   ```

### Problema: Lambda 2 não recebe notificação

1. Verifique o filtro SNS no template.yaml
2. Verifique os logs da Lambda 1 para ver se a notificação foi enviada
3. Verifique o tópico SNS:
   ```bash
   aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:...
   ```

### Problema: Erros na DLQ

1. Verifique mensagens na DLQ:
   ```bash
   aws sqs receive-message --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/video-frame-extraction-dlq
   ```

2. Analise os logs da Lambda para entender o erro
3. Corrija o problema e reprocesse as mensagens se necessário

## 📄 Licença

Este projeto faz parte do curso FIApx.

## 👥 Contribuidores

- [Seu Nome] - Lambda 1 e Lambda 2

## 🔗 Links Úteis

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [OpenCV Documentation](https://docs.opencv.org/)
