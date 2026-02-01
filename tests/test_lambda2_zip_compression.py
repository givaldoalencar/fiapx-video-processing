"""
Testes unitários para Lambda 2 - ZIP Compression
"""

import pytest
import json
import os
import tempfile
import zipfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Adicionar o diretório da lambda ao path
lambda2_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lambda2_zip_compression'))
if lambda2_path not in sys.path:
    # Remover lambda1 do path se estiver lá
    lambda1_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lambda1_frame_extraction'))
    if lambda1_path in sys.path:
        sys.path.remove(lambda1_path)
    sys.path.insert(0, lambda2_path)

# Importar especificamente do módulo lambda2
import importlib.util
spec = importlib.util.spec_from_file_location("handler_lambda2", os.path.join(lambda2_path, "handler.py"))
handler_lambda2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler_lambda2)

# Importar funções
download_frames_from_s3 = handler_lambda2.download_frames_from_s3
create_zip_file = handler_lambda2.create_zip_file
upload_zip_to_s3 = handler_lambda2.upload_zip_to_s3
notify_completion = handler_lambda2.notify_completion
lambda_handler = handler_lambda2.lambda_handler


class TestDownloadFramesFromS3:
    """Testes para download de frames do S3"""
    
    @patch.object(handler_lambda2, 's3_client')
    def test_download_frames_success(self, mock_s3_client):
        """Testa download bem-sucedido de frames"""
        # Mock do paginator
        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        
        # Mock das páginas
        mock_page = {
            'Contents': [
                {'Key': 'frames/video/frame_000000.jpg'},
                {'Key': 'frames/video/frame_000001.jpg'},
                {'Key': 'frames/video/readme.txt'}  # Deve ser ignorado
            ]
        }
        mock_paginator.paginate.return_value = [mock_page]
        mock_s3_client.download_file.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            frames = download_frames_from_s3('test-bucket', 'frames/video/', temp_dir)
            
            # Deve baixar apenas os arquivos de imagem
            assert len(frames) == 2
            assert mock_s3_client.download_file.call_count == 2
    
    @patch.object(handler_lambda2, 's3_client')
    def test_download_frames_no_frames_found(self, mock_s3_client):
        """Testa erro quando nenhum frame é encontrado"""
        mock_paginator = MagicMock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{'Contents': []}]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Nenhum frame encontrado"):
                download_frames_from_s3('test-bucket', 'frames/video/', temp_dir)


class TestCreateZipFile:
    """Testes para criação de arquivo ZIP"""
    
    def test_create_zip_file_success(self):
        """Testa criação bem-sucedida de arquivo ZIP"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Criar arquivos de frame mock
            frame1 = os.path.join(temp_dir, "frame_000000.jpg")
            frame2 = os.path.join(temp_dir, "frame_000001.jpg")
            
            with open(frame1, 'wb') as f:
                f.write(b"dummy frame 1")
            with open(frame2, 'wb') as f:
                f.write(b"dummy frame 2")
            
            frames = [frame1, frame2]
            zip_path = os.path.join(temp_dir, "test.zip")
            
            result = create_zip_file(frames, zip_path, "test-video")
            
            assert result == zip_path
            assert os.path.exists(zip_path)
            
            # Verificar conteúdo do ZIP
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                files = zipf.namelist()
                assert 'frame_000000.jpg' in files
                assert 'frame_000001.jpg' in files
                assert len(files) == 2
    
    def test_create_zip_file_missing_frame(self):
        """Testa criação de ZIP quando um frame não existe"""
        with tempfile.TemporaryDirectory() as temp_dir:
            frame1 = os.path.join(temp_dir, "frame_000000.jpg")
            frame2 = os.path.join(temp_dir, "nonexistent.jpg")
            
            with open(frame1, 'wb') as f:
                f.write(b"dummy")
            
            frames = [frame1, frame2]
            zip_path = os.path.join(temp_dir, "test.zip")
            
            # Não deve lançar exceção, apenas ignorar o arquivo inexistente
            result = create_zip_file(frames, zip_path, "test-video")
            
            assert os.path.exists(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                assert len(zipf.namelist()) == 1


class TestUploadZipToS3:
    """Testes para upload de ZIP para S3"""
    
    @patch.object(handler_lambda2, 's3_client')
    def test_upload_zip_success(self, mock_s3_client):
        """Testa upload bem-sucedido de ZIP"""
        mock_s3_client.upload_file.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "test.zip")
            with open(zip_path, 'wb') as f:
                f.write(b"dummy zip content")
            
            s3_key = upload_zip_to_s3(zip_path, "test-bucket", "test-video")
            
            assert s3_key == "zips/test-video_frames.zip"
            mock_s3_client.upload_file.assert_called_once_with(
                zip_path, "test-bucket", s3_key
            )


class TestNotifyCompletion:
    """Testes para notificação de conclusão"""
    
    @patch.object(handler_lambda2, 'sns_client')
    @patch.object(handler_lambda2, 'SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    def test_notify_completion_success(self, mock_sns_client):
        """Testa notificação bem-sucedida"""
        notify_completion("test-video", 10, "zips/test-video_frames.zip", success=True)
        
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        assert call_args[1]['TopicArn'] == 'arn:aws:sns:us-east-1:123456789012:test-topic'
        
        message = json.loads(call_args[1]['Message'])
        assert message['status'] == 'completed'
        assert message['frames_count'] == 10
        assert message['zip_key'] == "zips/test-video_frames.zip"


class TestLambdaHandler:
    """Testes para o handler principal da Lambda 2"""
    
    @patch.object(handler_lambda2, 'download_frames_from_s3')
    @patch.object(handler_lambda2, 'create_zip_file')
    @patch.object(handler_lambda2, 'upload_zip_to_s3')
    @patch.object(handler_lambda2, 'notify_completion')
    @patch.object(handler_lambda2, 'FRAMES_BUCKET', 'test-frames-bucket')
    @patch.object(handler_lambda2, 'OUTPUT_BUCKET', 'test-output-bucket')
    def test_lambda_handler_success(self, mock_notify, mock_upload, 
                                    mock_create_zip, mock_download):
        """Testa execução bem-sucedida do handler"""
        # Configurar mocks
        with tempfile.TemporaryDirectory() as temp_dir:
            frame1 = os.path.join(temp_dir, "frame_000000.jpg")
            frame2 = os.path.join(temp_dir, "frame_000001.jpg")
            with open(frame1, 'w') as f:
                f.write("dummy")
            with open(frame2, 'w') as f:
                f.write("dummy")
            
            mock_download.return_value = [frame1, frame2]
            mock_create_zip.return_value = os.path.join(temp_dir, "test.zip")
            mock_upload.return_value = "zips/test-video_frames.zip"
            
            # Evento SNS
            event = {
                'Records': [{
                    'Sns': {
                        'Message': json.dumps({
                            'video_key': 'test-video.mp4',
                            'frames_prefix': 'frames/test-video/',
                            'frames_count': 2
                        })
                    }
                }]
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['processed'] == 1
            assert body['failed'] == 0
            mock_download.assert_called_once()
            mock_create_zip.assert_called_once()
            mock_upload.assert_called_once()
            mock_notify.assert_called_once()
    
    @patch.object(handler_lambda2, 'FRAMES_BUCKET', '')
    @patch.object(handler_lambda2, 'OUTPUT_BUCKET', '')
    def test_lambda_handler_missing_buckets(self):
        """Testa erro quando buckets não estão configurados"""
        event = {'Records': []}
        
        with pytest.raises(ValueError, match="FRAMES_BUCKET e OUTPUT_BUCKET"):
            lambda_handler(event, None)
    
    @patch.object(handler_lambda2, 'download_frames_from_s3')
    @patch.object(handler_lambda2, 'FRAMES_BUCKET', 'test-frames-bucket')
    @patch.object(handler_lambda2, 'OUTPUT_BUCKET', 'test-output-bucket')
    def test_lambda_handler_missing_frames_prefix(self, mock_download):
        """Testa erro quando frames_prefix não está na mensagem"""
        event = {
            'Records': [{
                'Sns': {
                    'Message': json.dumps({
                        'video_key': 'test-video.mp4'
                        # frames_prefix ausente
                    })
                }
            }]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 207  # Multi-Status
        body = json.loads(response['body'])
        assert body['processed'] == 0
        assert body['failed'] == 1
        assert len(body['errors']) == 1
    
    @patch.object(handler_lambda2, 'download_frames_from_s3')
    @patch.object(handler_lambda2, 'create_zip_file')
    @patch.object(handler_lambda2, 'upload_zip_to_s3')
    @patch.object(handler_lambda2, 'notify_completion')
    @patch.object(handler_lambda2, 'FRAMES_BUCKET', 'test-frames-bucket')
    @patch.object(handler_lambda2, 'OUTPUT_BUCKET', 'test-output-bucket')
    def test_lambda_handler_multiple_records(self, mock_notify, mock_upload,
                                             mock_create_zip, mock_download):
        """Testa processamento de múltiplas mensagens SNS"""
        with tempfile.TemporaryDirectory() as temp_dir:
            frame1 = os.path.join(temp_dir, "frame_000000.jpg")
            with open(frame1, 'w') as f:
                f.write("dummy")
            
            mock_download.return_value = [frame1]
            mock_create_zip.return_value = os.path.join(temp_dir, "test.zip")
            mock_upload.return_value = "zips/test-video_frames.zip"
            
            event = {
                'Records': [
                    {
                        'Sns': {
                            'Message': json.dumps({
                                'video_key': 'video1.mp4',
                                'frames_prefix': 'frames/video1/'
                            })
                        }
                    },
                    {
                        'Sns': {
                            'Message': json.dumps({
                                'video_key': 'video2.mp4',
                                'frames_prefix': 'frames/video2/'
                            })
                        }
                    }
                ]
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['total'] == 2
