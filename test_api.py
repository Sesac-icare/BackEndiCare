import requests

def test_ocr_api():
    url = 'http://localhost:8000/api/prescriptions/ocr/'
    
    # 이미지 파일과 데이터 준비
    files = {
        'image': open('path/to/your/image.jpg', 'rb')
    }
    data = {
        'child_id': 1
    }
    
    # API 요청
    response = requests.post(url, files=files, data=data)
    
    # 결과 출력
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == '__main__':
    test_ocr_api() 