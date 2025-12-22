# CDSS JWT 적용 로드맵 (0단계 ~ 6단계)

> 목표: Django(HTTP) + Channels(WS) + Celery + (BentoML/Mosec) 구조에서  
> Access/Refresh/Service 3종 토큰을 안전하게 적용한다.

---

## 0단계: 인증 경계 + 토큰 정책을 먼저 고정

JWT를 구현하기 전에 아래 항목을 문서로 확정한다.

1. **인증 대상(경계)**
   - HTTP API: Django(WSGI/ASGI)
   - WebSocket: Django Channels(ASGI)
   - 내부 호출: Celery/Django → BentoML/Mosec

2. **토큰 3종 정책**
   - Access Token TTL: 예) 5~10분
   - Refresh Token TTL: 예) 7~14일
   - Refresh Rotation/Blacklist: 권장 ON
   - Service Token TTL: 예) 30~60초

3. **aud 분리**
   - `cdss-api` (HTTP API)
   - `cdss-ws` (WebSocket)
   - `model-2d`, `model-3d` (모델 서버)

4. **클레임 최소 스펙**
   - 공통: `iss`, `sub`, `aud`, `exp`, `iat`, `jti`
   - 권한: `roles` 또는 `scope`
   - 멀티기관이면: `hospital_id` 또는 `tenant_id`

5. **저장/전달 방식**
   - 웹 기준: Refresh는 `HttpOnly + Secure` 쿠키 권장
   - Access는 Bearer 헤더 또는 쿠키 중 하나로 통일

6. **감사/추적(로그) 정책**
   - `jti`, `sub`, endpoint, 접근한 `patient_id/study_uid/series_uid` 등을 어느 수준으로 남길지 결정

---

## 1단계: Django에서 인증 뼈대 구축 (가장 먼저)

### 구현 항목
- `POST /auth/login`
  - ID/PW 검증 후 Access + Refresh 발급
- `POST /auth/refresh`
  - Refresh 검증 후 Access 재발급
  - (권장) Refresh Rotation 적용
- `POST /auth/logout`
  - Refresh 폐기(블랙리스트/DB)
- 보호 API에 JWT 인증/인가 적용
  - 기본 인증: `IsAuthenticated`
  - 역할/스코프 권한: Permission class 또는 데코레이터로 표준화

### 1차 테스트 체크리스트
- Access 만료 시 401
- Refresh로 재발급 성공
- Logout 이후 Refresh 재사용 차단(회전/블랙리스트 동작)

---

## 2단계: 프론트(또는 앱)에서 토큰 흐름 적용

### 구현 항목
- 로그인 성공 처리
  - Refresh: 쿠키(Set-Cookie)로 저장되는 방식이면 별도 저장 로직 불필요
  - Access: 결정한 방식(메모리/쿠키/스토리지)에 저장
- API 공통 호출 래퍼 구성(예: axios interceptor)
  - 401이면 `/auth/refresh` 호출
  - Access 갱신 후 원 요청 재시도

### 1차 테스트 체크리스트
- Access 만료 후 자동 갱신(401 → refresh → 재시도) 동작
- refresh 실패 시(만료/폐기) 로그인 화면 전환

---

## 3단계: Channels(WebSocket) 인증 적용

### 구현 항목
- WS 연결 시 AccessJWT 검증
  - 서명 검증 + exp 확인
  - `aud=cdss-ws` 확인
- 성공 시 사용자 컨텍스트 세팅
  - `scope.user` 세팅(또는 동등한 방식)
- 실패 시 연결 거절(close code 정책)

### 1차 테스트 체크리스트
- 토큰 없이 연결 거절
- 만료 토큰 거절
- `aud` 불일치 토큰 거절(예: cdss-api 토큰으로 ws 연결 시 실패)

---

## 4단계: Celery 작업 큐의 사용자 컨텍스트 전달 방식 확정

> 원칙: Celery task payload에 사용자 AccessJWT 자체를 넣지 않는다.  
> 최소 정보만 전달하고, 필요하면 DB에서 재확인한다.

### Enqueue 시 Django가 넣는 값(추천)
- `job_id`
- `requested_by_user_id` (sub)
- `request_jti`
- `study_uid` / `series_uid`
- `model_type` (2d/3d)
- 기타 최소 파라미터

### Worker 실행 시
- DB에서 job 상태/권한/대상 리소스 재확인(필요 시)
- 모델 서버 호출은 **ServiceJWT를 실행 시점에 생성**하여 사용

---

## 5단계: BentoML/Mosec에 ServiceJWT 검증 적용

### 원칙
- 모델 서버는 사용자 AccessJWT를 받지 않는다.
- **ServiceJWT만 허용**하도록 고정한다.

### 구현 항목
- 요청 헤더:
  - `Authorization: Bearer <ServiceJWT>`
- 검증 규칙:
  - `aud=model-2d` 또는 `aud=model-3d`
  - `exp` 매우 짧게(30~60초)
  - `sub=service:celery` 등 서비스 주체 확인
- 실패 처리:
  - 토큰 없음/만료: 401
  - aud 불일치/권한 부족: 403(정책에 따라)

### 1차 테스트 체크리스트
- ServiceJWT 없으면 401
- aud 틀리면 거절
- 만료면 거절
- 정상 ServiceJWT면 추론 진행

---

## 6단계: 키/시크릿 운영(배포 관점 정리)

### RS256(권장: 다중 서비스 검증 환경)
- 개인키: 발급 주체(Django 또는 IdP)만 보관
- 공개키: JWKS로 배포하거나 안전한 방식으로 공유
- 키 교체(kid/rotation) 전략 수립

### HS256(단일 서비스에는 단순)
- 모든 검증 주체가 동일 secret을 공유해야 함
- 서비스가 늘어날수록 키 관리/유출 위험이 커질 수 있음

### 운영 체크리스트
- 키/시크릿 교체(로테이션) 정책
- 토큰 로그 마스킹(운영 로그에 토큰 원문 출력 금지)
- 감사로그 설계(jti 기반 추적)

---

## 최종 권장 실행 순서 요약

1) 0단계: 정책 문서 고정  
2) 1단계: Django 인증(발급/검증/권한)  
3) 2단계: 프론트 토큰 갱신 흐름(401 → refresh)  
4) 3단계: Channels WS 연결 인증  
5) 4단계: Celery payload 최소화 + 실행 시점 ServiceJWT 발급  
6) 5단계: 모델 서버 ServiceJWT 검증  
7) 6단계: 키 운영(JWKS/rotation) 정리
