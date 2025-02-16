from django.core.management.base import BaseCommand
from django.db import transaction
from searchPharmacy.models import Pharmacy
from searchPharmacy.pharmacy_updater import fetch_all_pharmacies

class Command(BaseCommand):
    help = '공공 API에서 약국 정보를 가져와 DB를 업데이트합니다'

    def handle(self, *args, **options):
        self.stdout.write('약국 정보 업데이트 시작...')
        
        pharmacies = fetch_all_pharmacies()
        
        if not pharmacies:
            self.stdout.write(self.style.ERROR('데이터 가져오기 실패'))
            return
        
        try:
            with transaction.atomic():
                # 기존 데이터 삭제
                Pharmacy.objects.all().delete()
                
                # 새 데이터 생성
                pharmacy_objects = []
                for data in pharmacies:
                    pharmacy = Pharmacy(
                        name=data['name'],
                        address=data['addr'],
                        tel=data['tel'],
                        fax=data['fax'],
                        latitude=data['lat'],
                        longitude=data['lon'],
                        map_info=data['map_info'],
                        etc=data['etc'],
                        
                        # 운영시간
                        mon_start=data['operating_hours']['월']['start'],
                        mon_end=data['operating_hours']['월']['end'],
                        tue_start=data['operating_hours']['화']['start'],
                        tue_end=data['operating_hours']['화']['end'],
                        wed_start=data['operating_hours']['수']['start'],
                        wed_end=data['operating_hours']['수']['end'],
                        thu_start=data['operating_hours']['목']['start'],
                        thu_end=data['operating_hours']['목']['end'],
                        fri_start=data['operating_hours']['금']['start'],
                        fri_end=data['operating_hours']['금']['end'],
                        sat_start=data['operating_hours']['토']['start'],
                        sat_end=data['operating_hours']['토']['end'],
                        sun_start=data['operating_hours']['일']['start'],
                        sun_end=data['operating_hours']['일']['end'],
                    )
                    pharmacy_objects.append(pharmacy)
                
                # 벌크 생성
                Pharmacy.objects.bulk_create(pharmacy_objects)
                
                self.stdout.write(
                    self.style.SUCCESS(f'성공적으로 {len(pharmacy_objects)}개의 약국 정보를 업데이트했습니다')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'데이터 저장 중 오류 발생: {str(e)}')
            ) 