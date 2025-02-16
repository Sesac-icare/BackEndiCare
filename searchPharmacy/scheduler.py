from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.core.management import call_command
from datetime import datetime
import logging
import sys

logger = logging.getLogger('searchPharmacy')

def start():
    # 중복 실행 방지
    if 'runserver' not in sys.argv:  # 개발 서버에서만 실행
        scheduler = BackgroundScheduler()
        scheduler.add_jobstore(DjangoJobStore(), "default")
        
        # 기존 작업이 있다면 제거
        scheduler.remove_all_jobs()
        
        # 매일 새벽 3시에 실행
        scheduler.add_job(
            update_pharmacy_data,
            'cron',
            hour=3,
            minute=0,
            name='pharmacy_update',
            jobstore='default',
            replace_existing=True
        )
        
        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

def update_pharmacy_data():
    try:
        logger.info(f"약국 데이터 업데이트 시작: {datetime.now()}")
        call_command('update_pharmacies')
        logger.info(f"약국 데이터 업데이트 완료: {datetime.now()}")
    except Exception as e:
        logger.error(f"약국 데이터 업데이트 실패: {str(e)}") 