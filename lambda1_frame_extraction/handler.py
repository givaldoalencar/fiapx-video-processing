"""
Lambda 1: Frame Extraction
Processa vídeo e extrai frames salvando em bucket S3
"""

import json
import os
import boto3
import tempfile
import logging
from typing import Dict, Any, List
import cv2
from pathlib import Path
from urllib.parse import unquote_plus

# Configurar logging estruturado
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Inicializar clientes AWS
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')

# Variáveis de ambiente
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
FRAMES_PER_SECOND = float(os.environ.get('FRAMES_PER_SECOND', '1.0'))

# Formatos de vídeo suportados
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}


def validate_video_file(video_key: str) -> None:
    """
    Valida se o arquivo é um vídeo suportado
    
    Args:
        video_key: Chave do arquivo no S3
    
    Raises:
        ValueError: Se o formato não for suportado
    """
    file_ext = Path(video_key).suffix.lower()
    if file_ext not in SUPPORTED_VIDEO_FORMATS:
        raise ValueError(
            f"Formato de vídeo não suportado: {file_ext}. "
            f"Formatos suportados: {', '.join(SUPPORTED_VIDEO_FORMATS)}"
        )


def extract_frames(video_path: str, output_dir: str, fps: float = 1.0) -> List[str]:
    """
    Extrai frames do vídeo e salva como imagens
    
    Args:
        video_path: Caminho do arquivo de vídeo
        output_dir: Diretório de saída para os frames
        fps: Frames por segundo a serem extraídos
    
    Returns:
        Lista com os caminhos dos frames extraídos
    
    Raises:
        ValueError: Se não conseguir abrir o vídeo ou extrair frames
    """
    frames = []
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Não foi possível abrir o vídeo: {video_path}")
    
    try:
        # Obter FPS do vídeo
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps <= 0:
            raise ValueError(f"FPS inválido do vídeo: {video_fps}")
        
        frame_interval = int(video_fps / fps) if fps > 0 else 1
        if frame_interval < 1:
            frame_interval = 1
        
        frame_count = 0
        saved_count = 0
        
        logger.info(f"Extraindo frames: FPS do vídeo={video_fps}, Intervalo={frame_interval}")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Salvar frame apenas no intervalo especificado
            if frame_count % frame_interval == 0:
                frame_filename = f"frame_{saved_count:06d}.jpg"
                frame_path = os.path.join(output_dir, frame_filename)
                
                if not cv2.imwrite(frame_path, frame):
                    logger.warning(f"Falha ao salvar frame: {frame_path}")
                else:
                    frames.append(frame_path)
                    saved_count += 1
            
            frame_count += 1
        
        if not frames:
            raise ValueError("Nenhum frame foi extraído do vídeo")
        
        logger.info(f"Total de frames extraídos: {len(frames)}")
        
    finally:
        cap.release()
    
    return frames


def upload_frames_to_s3(frames: List[str], bucket: str, video_key: str) -> List[str]:
    """
    Faz upload dos frames para o bucket S3
    
    Args:
        frames: Lista de caminhos dos frames
        bucket: Nome do bucket de destino
        video_key: Chave do vídeo original (para criar estrutura de pastas)
    
    Returns:
        Lista de chaves S3 dos frames enviados
    
    Raises:
        Exception: Se houver erro no upload
    """
    # Extrair nome do vídeo sem extensão
    video_name = Path(video_key).stem
    s3_keys = []
    
    logger.info(f"Iniciando upload de {len(frames)} frames para s3://{bucket}/frames/{video_name}/")
    
    for idx, frame_path in enumerate(frames):
        try:
            frame_filename = os.path.basename(frame_path)
            s3_key = f"frames/{video_name}/{frame_filename}"
            
            s3_client.upload_file(frame_path, bucket, s3_key)
            s3_keys.append(s3_key)
            
            if (idx + 1) % 10 == 0:
                logger.info(f"Upload progress: {idx + 1}/{len(frames)} frames")
        
        except Exception as e:
            logger.error(f"Erro ao fazer upload do frame {frame_path}: {str(e)}")
            raise
    
    logger.info(f"Upload concluído: {len(s3_keys)} frames enviados")
    return s3_keys


def notify_completion(video_key: str, frames_count: int, frames_prefix: str, success: bool = True):
    """
    Notifica conclusão do processamento via SNS
    
    Args:
        video_key: Chave do vídeo processado
        frames_count: Número de frames extraídos
        frames_prefix: Prefixo dos frames no S3
        success: Se o processamento foi bem-sucedido
    """
    if not SNS_TOPIC_ARN:
        return
    
    message = {
        'video_key': video_key,
        'frames_count': frames_count,
        'frames_prefix': frames_prefix,
        'status': 'completed' if success else 'failed',
        'lambda': 'lambda1_frame_extraction'
    }
    
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message),
            Subject=f"Video Processing {'Completed' if success else 'Failed'}"
        )
    except Exception as e:
        print(f"Erro ao enviar notificação SNS: {str(e)}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler principal da Lambda 1
    
    Event structure:
    {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket-name"},
                    "object": {"key": "video-key"}
                }
            }
        ]
    }
    """
    # Validar variáveis de ambiente
    if not OUTPUT_BUCKET:
        logger.error("OUTPUT_BUCKET não configurado")
        raise ValueError("OUTPUT_BUCKET não configurado")
    
    records = event.get('Records', [])
    if not records:
        logger.warning("Nenhum record encontrado no evento")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Nenhum record encontrado no evento'})
        }
    
    logger.info(f"Processando {len(records)} vídeo(s)")
    
    results = []
    errors = []
    
    # Processar cada evento S3
    for idx, record in enumerate(records):
        try:
            bucket_name = record['s3']['bucket']['name']
            # Decodificar a chave do objeto (espaços podem vir como + ou %20)
            video_key = unquote_plus(record['s3']['object']['key'])
            
            logger.info(f"[{idx+1}/{len(records)}] Processando vídeo: s3://{bucket_name}/{video_key}")
            
            # Validar se é um arquivo de vídeo
            try:
                validate_video_file(video_key)
            except ValueError as e:
                logger.error(f"Validação falhou para {video_key}: {str(e)}")
                errors.append({
                    'video_key': video_key,
                    'error': str(e)
                })
                continue
            
            # Criar diretório temporário
            with tempfile.TemporaryDirectory() as temp_dir:
                frames_dir = os.path.join(temp_dir, 'frames')
                os.makedirs(frames_dir, exist_ok=True)
                
                # Download do vídeo
                video_path = os.path.join(temp_dir, os.path.basename(video_key))
                logger.info(f"Baixando vídeo: s3://{bucket_name}/{video_key}")
                s3_client.download_file(bucket_name, video_key, video_path)
                
                # Extrair frames
                logger.info(f"Extraindo frames do vídeo...")
                frames = extract_frames(video_path, frames_dir, FRAMES_PER_SECOND)
                
                if not frames:
                    raise ValueError("Nenhum frame foi extraído do vídeo")
                
                # Upload dos frames para S3
                video_name = Path(video_key).stem
                frames_prefix = f"frames/{video_name}/"
                logger.info(f"Fazendo upload de {len(frames)} frames para S3...")
                s3_keys = upload_frames_to_s3(frames, OUTPUT_BUCKET, video_key)
                
                logger.info(f"✅ Vídeo processado com sucesso: {len(frames)} frames extraídos. Prefixo: {frames_prefix}")
                
                # Notificar conclusão
                notify_completion(video_key, len(frames), frames_prefix, success=True)
                
                results.append({
                    'video_key': video_key,
                    'frames_count': len(frames),
                    'frames_prefix': frames_prefix,
                    'status': 'success'
                })
        
        except Exception as e:
            error_message = f"Erro ao processar vídeo: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Tentar obter video_key para notificação
            video_key = 'unknown'
            try:
                video_key = unquote_plus(record.get('s3', {}).get('object', {}).get('key', 'unknown'))
            except:
                pass
            
            # Notificar erro
            notify_completion(video_key, 0, '', success=False)
            
            errors.append({
                'video_key': video_key,
                'error': error_message
            })
    
    # Preparar resposta
    status_code = 200 if not errors else 207  # 207 = Multi-Status (alguns sucessos, alguns erros)
    
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

