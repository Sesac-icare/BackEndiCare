from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from children.models import Children
from users.models import User

class OCRAPITestCase(TestCase):
    def setUp(self):
        # 테스트용 사용자와 자녀 생성
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.child = Children.objects.create(
            user=self.user,
            child_name='Test Child'
        )
        self.client = APIClient()
        
    def test_ocr_api(self):
        # 테스트용 이미지 파일 생성
        image = SimpleUploadedFile(
            name='test_image.jpg',
            content=open('path/to/test/image.jpg', 'rb').read(),
            content_type='image/jpeg'
        )
        
        # API 요청
        response = self.client.post('/api/prescriptions/ocr/', {
            'image': image,
            'child_id': self.child.child_id
        }, format='multipart')
        
        # 응답 검증
        self.assertEqual(response.status_code, 201)
        self.assertIn('envelope_id', response.data)
