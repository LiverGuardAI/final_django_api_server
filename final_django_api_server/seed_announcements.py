"""
병원 공지사항 테스트 데이터 생성 스크립트
Django shell에서 실행: python manage.py shell < seed_announcements.py
"""
from datetime import datetime, timedelta
from doctor.models import Announcement
from accounts.models import CustomUser

# 관리자 계정 가져오기 (없으면 첫 번째 사용자)
try:
    author = CustomUser.objects.filter(is_staff=True).first() or CustomUser.objects.first()
except:
    author = None

# 테스트 공지사항 데이터
announcements_data = [
    {
        'title': '2026년 설날 연휴 진료 안내',
        'content': '설날 연휴 기간(1/28~1/30) 응급실만 24시간 운영됩니다. 외래 진료는 1/31(금)부터 정상 운영됩니다. 불편을 드려 죄송합니다.',
        'announcement_type': 'GENERAL',
        'is_important': True,
        'published_at': datetime.now(),
        'expires_at': datetime.now() + timedelta(days=20),
    },
    {
        'title': '[긴급] 병원 전산시스템 점검 안내',
        'content': '1/20(월) 02:00~06:00 전산시스템 정기 점검이 예정되어 있습니다. 해당 시간에는 처방전 발급 및 수납이 일시 중단될 수 있으니 양해 부탁드립니다.',
        'announcement_type': 'URGENT',
        'is_important': True,
        'published_at': datetime.now() - timedelta(days=5),
        'expires_at': datetime.now() + timedelta(days=7),
    },
    {
        'title': '간암 조기검진 무료 상담 행사 안내',
        'content': '2월 한 달간 간암 고위험군 환자를 대상으로 무료 상담 및 초음파 검사를 진행합니다. 소화기내과 외래로 문의 바랍니다. (문의: 02-1234-5678)',
        'announcement_type': 'EVENT',
        'is_important': False,
        'published_at': datetime.now() - timedelta(days=2),
        'expires_at': datetime.now() + timedelta(days=45),
    },
    {
        'title': '주차장 이용 안내',
        'content': '본관 주차장 공사로 인해 1/15~2/28까지 별관 주차장을 이용해 주시기 바랍니다. 외래 환자분들께서는 주차권을 원무과에서 발급받으실 수 있습니다.',
        'announcement_type': 'GENERAL',
        'is_important': False,
        'published_at': datetime.now() - timedelta(days=10),
        'expires_at': datetime.now() + timedelta(days=50),
    },
    {
        'title': '소화기내과 김영수 교수 진료 일정 변경',
        'content': '김영수 교수님의 목요일 오후 외래 진료가 학회 참석으로 인해 1월 한 달간 휴진합니다. 대신 금요일 오전 진료를 추가로 운영하오니 참고 바랍니다.',
        'announcement_type': 'GENERAL',
        'is_important': True,
        'published_at': datetime.now() - timedelta(days=7),
        'expires_at': datetime.now() + timedelta(days=20),
    },
    {
        'title': '병원 내 감염 예방 수칙 안내',
        'content': '독감 유행 시즌입니다. 병원 내에서는 반드시 마스크를 착용해 주시고, 손 소독제를 자주 이용해 주시기 바랍니다. 발열 증상이 있으신 분은 선별진료소를 먼저 방문해 주세요.',
        'announcement_type': 'URGENT',
        'is_important': True,
        'published_at': datetime.now() - timedelta(days=15),
        'expires_at': datetime.now() + timedelta(days=60),
    },
    {
        'title': '건강강좌: 간 건강 지키는 생활습관',
        'content': '1/25(목) 14:00 본관 2층 대강당에서 "간 건강 지키는 생활습관"을 주제로 건강강좌를 진행합니다. 소화기내과 이지은 교수님께서 강연하십니다. 참가비 무료.',
        'announcement_type': 'EVENT',
        'is_important': False,
        'published_at': datetime.now() - timedelta(days=3),
        'expires_at': datetime.now() + timedelta(days=12),
    },
    {
        'title': '진료비 수납 방법 안내',
        'content': '진료비는 1층 수납창구, 무인수납기, 모바일 앱을 통해 결제 가능합니다. 카드/현금 모두 가능하며, 영수증은 재발급이 가능합니다.',
        'announcement_type': 'GENERAL',
        'is_important': False,
        'published_at': datetime.now() - timedelta(days=30),
        'expires_at': None,
    },
    {
        'title': '영상의학과 MRI 장비 업그레이드 완료',
        'content': '최신 3.0T MRI 장비 도입으로 더욱 정밀한 검사가 가능해졌습니다. 간암 진단의 정확도가 향상되었으며, 검사 시간도 단축되었습니다.',
        'announcement_type': 'GENERAL',
        'is_important': False,
        'published_at': datetime.now() - timedelta(days=20),
        'expires_at': datetime.now() + timedelta(days=30),
    },
    {
        'title': '[시스템점검] 모바일 앱 서비스 일시 중단',
        'content': '1/18(목) 23:00~1/19(금) 01:00 모바일 앱 업데이트로 인해 서비스가 일시 중단됩니다. 진료 예약 및 결과 조회는 PC 웹사이트를 이용해 주시기 바랍니다.',
        'announcement_type': 'MAINTENANCE',
        'is_important': True,
        'published_at': datetime.now() - timedelta(days=1),
        'expires_at': datetime.now() + timedelta(days=5),
    },
]

# 기존 공지사항 삭제 (선택사항)
print("기존 공지사항 삭제 중...")
Announcement.objects.all().delete()

# 새 공지사항 생성
print("새 공지사항 생성 중...")
created_count = 0
for data in announcements_data:
    announcement = Announcement.objects.create(
        author=author,
        **data
    )
    created_count += 1
    print(f"✅ {created_count}. {announcement.title}")

print(f"\n총 {created_count}개의 공지사항이 생성되었습니다.")
