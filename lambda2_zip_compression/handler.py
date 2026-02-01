"""
Lambda 2: ZIP Compression
Compacta imagens geradas pela Lambda 1 em um arquivo ZIP
"""

import json
import os
import boto3
import tempfile
import zipfile
import logging
from typing import Dict, Any, List
from pathlib import Path

# Configurar logging estruturado
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Inicializar clientes AWS com região padrão
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sns_client = boto3.client('sns', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Variáveis de ambiente
FRAMES_BUCKET = os.environ.get('FRAMES_BUCKET')  # Bucket onde os frames estão (mesmo do OUTPUT da Lambda 1)
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')


def download_frames_from_s3(bucket: str, frames_prefix: str, temp_dir: str) -> List[str]:
    """
    Faz download de todos os frames do prefixo especificado
    
    Args:
        bucket: Nome do bucket S3
        frames_prefix: Prefixo dos frames no S3
        temp_dir: Diretório temporário para salvar os frames
    
    Returns:
        Lista com os caminhos locais dos frames baixados
    
    Raises:
        ValueError: Se nenhum frame for encontrado
    """
    frames = []
    
    logger.info(f"Listando frames em s3://{bucket}/{frames_prefix}")
    
    # Listar objetos no prefixo
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=frames_prefix)
        
        for page in pages:
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                key = obj['Key']
                
                # Verificar se é um arquivo de imagem
                if not key.lower().endswith(('.jpg', '.jpeg', '.png')):
                    logger.debug(f"Ignorando arquivo não-imagem: {key}")
                    continue
                
                # Download do arquivo
                try:
                    local_path = os.path.join(temp_dir, os.path.basename(key))
                    s3_client.download_file(bucket, key, local_path)
                    frames.append(local_path)
                    
                    if len(frames) % 10 == 0:
                        logger.info(f"Download progress: {len(frames)} frames baixados")
                
                except Exception as e:
                    logger.error(f"Erro ao baixar frame {key}: {str(e)}")
                    raise
        
        if not frames:
            raise ValueError(f"Nenhum frame encontrado no prefixo: {frames_prefix}")
        
        logger.info(f"Total de {len(frames)} frames baixados")
        
    except Exception as e:
        logger.error(f"Erro ao listar/baixar frames: {str(e)}")
        raise
    
    return sorted(frames)


def create_zip_file(frames: List[str], output_path: str, video_name: str) -> str:
    """
    Cria arquivo ZIP com os frames
    
    Args:
        frames: Lista de caminhos dos frames
        output_path: Caminho do arquivo ZIP de saída
        video_name: Nome do vídeo (para nomear o ZIP)
    
    Returns:
        Caminho do arquivo ZIP criado
    
    Raises:
        Exception: Se houver erro ao criar o ZIP
    """
    logger.info(f"Criando arquivo ZIP com {len(frames)} frames: {output_path}")
    
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, frame_path in enumerate(frames):
                if not os.path.exists(frame_path):
                    logger.warning(f"Frame não encontrado: {frame_path}")
                    continue
                
                frame_name = os.path.basename(frame_path)
                # Adicionar frame ao ZIP mantendo apenas o nome do arquivo
                zipf.write(frame_path, arcname=frame_name)
                
                if (idx + 1) % 10 == 0:
                    logger.debug(f"ZIP progress: {idx + 1}/{len(frames)} frames adicionados")
        
        # Verificar tamanho do arquivo criado
        zip_size = os.path.getsize(output_path)
        logger.info(f"ZIP criado com sucesso: {zip_size / (1024*1024):.2f} MB")
        
    except Exception as e:
        logger.error(f"Erro ao criar arquivo ZIP: {str(e)}", exc_info=True)
        raise
    
    return output_path


def upload_zip_to_s3(zip_path: str, bucket: str, video_name: str) -> str:
    """
    Faz upload do arquivo ZIP para o bucket S3
    
    Args:
        zip_path: Caminho do arquivo ZIP local
        bucket: Nome do bucket de destino
        video_name: Nome do vídeo
    
    Returns:
        Chave S3 do arquivo ZIP enviado
    
    Raises:
        Exception: Se houver erro no upload
    """
    zip_filename = f"{video_name}_frames.zip"
    s3_key = f"zips/{zip_filename}"
    
    logger.info(f"Fazendo upload do ZIP para s3://{bucket}/{s3_key}")
    
    try:
        s3_client.upload_file(zip_path, bucket, s3_key)
        logger.info(f"✅ ZIP enviado com sucesso: s3://{bucket}/{s3_key}")
    except Exception as e:
        logger.error(f"Erro ao fazer upload do ZIP: {str(e)}", exc_info=True)
        raise
    
    return s3_key


def notify_completion(video_name: str, frames_count: int, zip_key: str, success: bool = True):
    """
    Notifica conclusão do processamento via SNS
    
    Args:
        video_name: Nome do vídeo processado
        frames_count: Número de frames compactados
        zip_key: Chave S3 do arquivo ZIP
        success: Se o processamento foi bem-sucedido
    """
    if not SNS_TOPIC_ARN:
        return
    
    message = {
        'video_name': video_name,
        'frames_count': frames_count,
        'zip_key': zip_key,
        'status': 'completed' if success else 'failed',
        'lambda': 'lambda2_zip_compression'
    }
    
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message),
            Subject=f"ZIP Compression {'Completed' if success else 'Failed'}"
        )
    except Exception as e:
        print(f"Erro ao enviar notificação SNS: {str(e)}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler principal da Lambda 2
    
    Event structure (from SNS):
    {
        "Records": [
            {
                "Sns": {
                    "Message": "{\"video_key\": \"...\", \"frames_prefix\": \"frames/video_name/\"}"
                }
            }
        ]
    }
    """
    # Validar variáveis de ambiente
    if not FRAMES_BUCKET or not OUTPUT_BUCKET:
        logger.error("FRAMES_BUCKET e OUTPUT_BUCKET devem estar configurados")
        raise ValueError("FRAMES_BUCKET e OUTPUT_BUCKET devem estar configurados")
    
    records = event.get('Records', [])
    if not records:
        logger.warning("Nenhum record encontrado no evento")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Nenhum record encontrado no evento'})
        }
    
    logger.info(f"Processando {len(records)} mensagem(ns) SNS")
    
    results = []
    errors = []
    
    # Processar cada mensagem SNS
    for idx, record in enumerate(records):
        try:
            # Parse da mensagem SNS
            sns_message_str = record.get('Sns', {}).get('Message', '{}')
            sns_message = json.loads(sns_message_str)
            
            frames_prefix = sns_message.get('frames_prefix', '')
            video_key = sns_message.get('video_key', '')
            
            # Validar campos obrigatórios
            if not frames_prefix:
                raise ValueError("frames_prefix não encontrado na mensagem SNS")
            
            if not video_key:
                logger.warning("video_key não encontrado, tentando extrair do frames_prefix")
                # Tentar extrair do prefixo: frames/video_name/
                parts = frames_prefix.rstrip('/').split('/')
                if len(parts) >= 2:
                    video_key = parts[-1]
                else:
                    raise ValueError("Não foi possível determinar video_key")
            
            # Extrair nome do vídeo
            video_name = Path(video_key).stem if video_key else Path(frames_prefix).parts[-2] if len(Path(frames_prefix).parts) > 1 else 'unknown'
            
            logger.info(f"[{idx+1}/{len(records)}] Compactando frames: {frames_prefix} (vídeo: {video_name})")
            
            # Criar diretório temporário
            with tempfile.TemporaryDirectory() as temp_dir:
                frames_dir = os.path.join(temp_dir, 'frames')
                os.makedirs(frames_dir, exist_ok=True)
                
                # Download dos frames
                logger.info(f"Baixando frames de s3://{FRAMES_BUCKET}/{frames_prefix}")
                frames = download_frames_from_s3(FRAMES_BUCKET, frames_prefix, frames_dir)
                
                if not frames:
                    raise ValueError(f"Nenhum frame encontrado no prefixo: {frames_prefix}")
                
                logger.info(f"✅ {len(frames)} frames baixados com sucesso")
                
                # Criar arquivo ZIP
                zip_path = os.path.join(temp_dir, f"{video_name}_frames.zip")
                create_zip_file(frames, zip_path, video_name)
                
                # Upload do ZIP para S3
                zip_key = upload_zip_to_s3(zip_path, OUTPUT_BUCKET, video_name)
                
                logger.info(f"✅ Compactação concluída: s3://{OUTPUT_BUCKET}/{zip_key}")
                
                # Notificar conclusão
                notify_completion(video_name, len(frames), zip_key, success=True)
                
                results.append({
                    'video_name': video_name,
                    'video_key': video_key,
                    'frames_count': len(frames),
                    'zip_key': zip_key,
                    'status': 'success'
                })
        
        except Exception as e:
            error_message = f"Erro ao compactar frames: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Tentar obter informações do evento para notificação
            video_name = 'unknown'
            video_key = 'unknown'
            try:
                sns_message_str = record.get('Sns', {}).get('Message', '{}')
                sns_message = json.loads(sns_message_str)
                video_key = sns_message.get('video_key', 'unknown')
                video_name = sns_message.get('video_name', Path(video_key).stem if video_key != 'unknown' else 'unknown')
            except:
                pass
            
            # Notificar erro
            notify_completion(video_name, 0, '', success=False)
            
            errors.append({
                'video_name': video_name,
                'video_key': video_key,
                'error': error_message
            })
    
    # Preparar resposta
    status_code = 200 if not errors else 207  # 207 = Multi-Status
    
    response_body = {
        'processed': len(results),
        'failed': len(errors),
        'total': len(records)
    }
    
    if results:
        response_body['successful'] = results
    
    if errors:
        response_body['errors'] = errors
    
    logger.info(f"Processamento concluído: {len(results)} sucesso(s), {len(errors)} erro(s)")
    
    return {
        'statusCode': status_code,
        'body': json.dumps(response_body)
    }

