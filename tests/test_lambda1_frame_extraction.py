"""
Testes unitários para Lambda 1 - Frame Extraction
"""

import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Adicionar o diretório da lambda ao path
lambda1_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lambda1_frame_extraction'))
if lambda1_path not in sys.path:
    sys.path.insert(0, lambda1_path)

# Importar especificamente do módulo lambda1
import importlib.util
spec = importlib.util.spec_from_file_location("handler_lambda1", os.path.join(lambda1_path, "handler.py"))
handler_lambda1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler_lambda1)

# Importar funções
validate_video_file = handler_lambda1.validate_video_file
extract_frames = handler_lambda1.extract_frames
upload_frames_to_s3 = handler_lambda1.upload_frames_to_s3
notify_completion = handler_lambda1.notify_completion
lambda_handler = handler_lambda1.lambda_handler


class TestValidateVideoFile:
    """Testes para validação de arquivos de vídeo"""
    
    def test_valid_video_formats(self):
        """Testa formatos de vídeo válidos"""
        valid_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v']
        
        for fmt in valid_formats:
            assert validate_video_file(f"video{fmt}") is None
    
    def test_invalid_video_format(self):
        """Testa formato de vídeo inválido"""
        with pytest.raises(ValueError, match="Formato de vídeo não suportado"):
            validate_video_file("document.pdf")
    
    def test_case_insensitive(self):
        """Testa que a validação é case-insensitive"""
        assert validate_video_file("video.MP4") is None
        assert validate_video_file("video.AVI") is None


class TestExtractFrames:
    """Testes para extração de frames"""
    
    @patch.object(handler_lambda1, 'cv2')
    def test_extract_frames_success(self, mock_cv2):
        """Testa extração de frames bem-sucedida"""
        # Mock do VideoCapture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0  # 30 FPS
        mock_cap.read.side_effect = [
            (True, MagicMock()),  # Frame 0
            (True, MagicMock()),  # Frame 1
            (True, MagicMock()),  # Frame 2
            (False, None)  # Fim do vídeo
        ]
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.imwrite.return_value = True
        
        with tempfile.TemporaryDirectory() as temp_dir:
            frames = extract_frames("dummy_video.mp4", temp_dir, fps=1.0)
            
            # Com 30 FPS e fps=1.0, deveria extrair aproximadamente 3 frames
            assert len(frames) > 0
            mock_cap.release.assert_called_once()
    
    @patch.object(handler_lambda1, 'cv2')
    def test_extract_frames_video_not_opened(self, mock_cv2):
        """Testa erro quando vídeo não pode ser aberto"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.VideoCapture.return_value = mock_cap
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Não foi possível abrir o vídeo"):
                extract_frames("dummy_video.mp4", temp_dir, fps=1.0)
    
    @patch.object(handler_lambda1, 'cv2')
    def test_extract_frames_no_frames_extracted(self, mock_cv2):
        """Testa erro quando nenhum frame é extraído"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0
        mock_cap.read.return_value = (False, None)  # Vídeo vazio
        mock_cv2.VideoCapture.return_value = mock_cap
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Nenhum frame foi extraído"):
                extract_frames("dummy_video.mp4", temp_dir, fps=1.0)


class TestUploadFramesToS3:
    """Testes para upload de frames para S3"""
    
    @patch.object(handler_lambda1, 's3_client')
    def test_upload_frames_success(self, mock_s3_client):
        """Testa upload bem-sucedido de frames"""
        # Mock do upload_file para não fazer chamada real
        mock_s3_client.upload_file.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Criar arquivos de frame mock
            frame1 = os.path.join(temp_dir, "frame_000000.jpg")
            frame2 = os.path.join(temp_dir, "frame_000001.jpg")
            
            with open(frame1, 'w') as f:
                f.write("dummy")
            with open(frame2, 'w') as f:
                f.write("dummy")
            
            frames = [frame1, frame2]
            s3_keys = upload_frames_to_s3(frames, "test-bucket", "video.mp4")
            
            assert len(s3_keys) == 2
            assert mock_s3_client.upload_file.call_count == 2
            assert all("frames/" in key for key in s3_keys)


class TestNotifyCompletion:
    """Testes para notificação de conclusão"""
    
    @patch.object(handler_lambda1, 'sns_client')
    @patch.object(handler_lambda1, 'SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:test-topic')
    def test_notify_completion_success(self, mock_sns_client):
        """Testa notificação bem-sucedida"""
        notify_completion("video.mp4", 10, "frames/video/", success=True)
        
        mock_sns_client.publish.assert_called_once()
        call_args = mock_sns_client.publish.call_args
        assert call_args[1]['TopicArn'] == 'arn:aws:sns:us-east-1:123456789012:test-topic'
        
        message = json.loads(call_args[1]['Message'])
        assert message['status'] == 'completed'
        assert message['frames_count'] == 10
    
    @patch.object(handler_lambda1, 'sns_client')
    @patch.object(handler_lambda1, 'SNS_TOPIC_ARN', '')
    def test_notify_completion_no_topic(self, mock_sns_client):
        """Testa que não notifica quando SNS_TOPIC_ARN não está configurado"""
        notify_completion("video.mp4", 10, "frames/video/", success=True)
        mock_sns_client.publish.assert_not_called()


class TestLambdaHandler:
    """Testes para o handler principal da Lambda 1"""
    
    @patch.object(handler_lambda1, 'validate_video_file')
    @patch.object(handler_lambda1, 'extract_frames')
    @patch.object(handler_lambda1, 'upload_frames_to_s3')
    @patch.object(handler_lambda1, 'notify_completion')
    @patch.object(handler_lambda1, 's3_client')
    @patch.object(handler_lambda1, 'OUTPUT_BUCKET', 'test-output-bucket')
    @patch.object(handler_lambda1, 'FRAMES_PER_SECOND', 1.0)
    def test_lambda_handler_success(self, mock_s3_client, mock_notify, 
                                     mock_upload, mock_extract, mock_validate):
        """Testa execução bem-sucedida do handler"""
        # Configurar mocks
        mock_extract.return_value = ['frame1.jpg', 'frame2.jpg']
        mock_upload.return_value = ['frames/video/frame1.jpg', 'frames/video/frame2.jpg']
        mock_s3_client.download_file.return_value = None
        
        # Evento S3
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-input-bucket'},
                    'object': {'key': 'test-video.mp4'}
                }
            }]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['processed'] == 1
        assert body['failed'] == 0
        mock_validate.assert_called_once()
        mock_extract.assert_called_once()
        mock_upload.assert_called_once()
        mock_notify.assert_called_once()
    
    @patch.object(handler_lambda1, 'OUTPUT_BUCKET', '')
    def test_lambda_handler_missing_output_bucket(self):
        """Testa erro quando OUTPUT_BUCKET não está configurado"""
        event = {'Records': []}
        
        with pytest.raises(ValueError, match="OUTPUT_BUCKET não configurado"):
            lambda_handler(event, None)
    
    @patch.object(handler_lambda1, 'validate_video_file')
    @patch.object(handler_lambda1, 's3_client')
    @patch.object(handler_lambda1, 'OUTPUT_BUCKET', 'test-output-bucket')
    @patch.object(handler_lambda1, 'FRAMES_PER_SECOND', 1.0)
    def test_lambda_handler_invalid_video_format(self, mock_s3_client, mock_validate):
        """Testa tratamento de formato de vídeo inválido"""
        mock_validate.side_effect = ValueError("Formato não suportado")
        
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-input-bucket'},
                    'object': {'key': 'document.pdf'}
                }
            }]
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 207  # Multi-Status
        body = json.loads(response['body'])
        assert body['processed'] == 0
        assert body['failed'] == 1
        assert len(body['errors']) == 1
    
    @patch.object(handler_lambda1, 'validate_video_file')
    @patch.object(handler_lambda1, 's3_client')
    @patch.object(handler_lambda1, 'OUTPUT_BUCKET', 'test-output-bucket')
    @patch.object(handler_lambda1, 'FRAMES_PER_SECOND', 1.0)
    def test_lambda_handler_multiple_records(self, mock_s3_client, mock_validate):
        """Testa processamento de múltiplos eventos"""
        event = {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': 'test-input-bucket'},
                        'object': {'key': 'video1.mp4'}
                    }
                },
                {
                    's3': {
                        'bucket': {'name': 'test-input-bucket'},
                        'object': {'key': 'video2.mp4'}
                    }
                }
            ]
        }
        
        with patch.object(handler_lambda1, 'extract_frames', return_value=['frame1.jpg']):
            with patch.object(handler_lambda1, 'upload_frames_to_s3', return_value=['frames/video1/frame1.jpg']):
                with patch.object(handler_lambda1, 'notify_completion'):
                    response = lambda_handler(event, None)
                    
                    assert response['statusCode'] == 200
                    body = json.loads(response['body'])
                    assert body['total'] == 2
