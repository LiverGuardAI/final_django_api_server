import os
import requests
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([AllowAny])
def get_native_app_key(request):
    """
    카카오맵 JavaScript 키 반환
    Flutter 앱 초기화 시 이 API를 호출하여 앱 키 획득
    kakao_map_plugin은 WebView 기반이므로 JavaScript 키 필요
    """
    javascript_key = os.getenv('KAKAO_JAVASCRIPT_KEY', '')

    if not javascript_key:
        return Response({
            'error': 'Kakao JavaScript Key not configured'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'javascript_key': javascript_key
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_rest_api_key(request):
    """
    카카오 REST API 키 반환
    Flutter 앱에서 장소 검색 시 사용
    """
    rest_api_key = os.getenv('KAKAO_REST_API_KEY', '')

    if not rest_api_key:
        return Response({
            'error': 'Kakao REST API Key not configured'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'rest_api_key': rest_api_key
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_nearby_pharmacies(request):
    """
    Nearby pharmacy search (default radius 300m, size 15).
    """
    latitude = request.GET.get('latitude')
    longitude = request.GET.get('longitude')
    radius = request.GET.get('radius', '500')

    if not latitude or not longitude:
        return Response({
            'error': 'latitude and longitude are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    rest_api_key = os.getenv('KAKAO_REST_API_KEY', '')
    if not rest_api_key:
        return Response({
            'error': 'Kakao REST API Key not configured'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        url = 'https://dapi.kakao.com/v2/local/search/keyword.json'
        headers = {'Authorization': f'KakaoAK {rest_api_key}'}
        params = {
            'query': '\uc57d\uad6d',
            'x': longitude,
            'y': latitude,
            'radius': radius,
            'size': 15,
            'sort': 'distance'
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response({
                'error': f'Kakao API error: {response.status_code}',
                'details': response.text
            }, status=response.status_code)

    except Exception as e:
        return Response({
            'error': f'Search failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
@api_view(['GET'])
@permission_classes([AllowAny])
def search_pharmacies_by_query(request):
    """
    Keyword pharmacy search (size 15).
    """
    query = request.GET.get('query')

    if not query:
        return Response({
            'error': 'query is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    rest_api_key = os.getenv('KAKAO_REST_API_KEY', '')
    if not rest_api_key:
        return Response({
            'error': 'Kakao REST API Key not configured'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        url = 'https://dapi.kakao.com/v2/local/search/keyword.json'
        headers = {'Authorization': f'KakaoAK {rest_api_key}'}
        params = {
            'query': f'{query} \uc57d\uad6d',
            'size': 15
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response({
                'error': f'Kakao API error: {response.status_code}',
                'details': response.text
            }, status=response.status_code)

    except Exception as e:
        return Response({
            'error': f'Search failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def search_place_by_query(request):
    """
    Keyword place search (no pharmacy suffix)
    """
    query = request.GET.get('query')
    size = request.GET.get('size', '1')

    if not query:
        return Response({
            'error': 'query is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    rest_api_key = os.getenv('KAKAO_REST_API_KEY', '')
    if not rest_api_key:
        return Response({
            'error': 'Kakao REST API Key not configured'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        url = 'https://dapi.kakao.com/v2/local/search/keyword.json'
        headers = {'Authorization': f'KakaoAK {rest_api_key}'}
        params = {
            'query': query,
            'size': size
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        else:
            return Response({
                'error': f'Kakao API error: {response.status_code}',
                'details': response.text
            }, status=response.status_code)

    except Exception as e:
        return Response({
            'error': f'Search failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_map_html(request):
    """
    카카오맵이 포함된 HTML 페이지 반환
    Flutter WebView에서 이 HTML을 로드하여 지도 표시
    """
    javascript_key = os.getenv('KAKAO_MAP_JAVASCRIPT_KEY', '')

    if not javascript_key:
        return HttpResponse(
            '<html><body><h1>Kakao Map API key not configured</h1></body></html>',
            content_type='text/html'
        )

    html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>약국 찾기</title>
    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={javascript_key}&libraries=services&autoload=false"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100%; height: 100%; overflow: hidden; }}
        #map {{ width: 100%; height: 100%; }}
        #search-container {{ position: absolute; top: 10px; left: 10px; right: 10px; z-index: 1000; display: flex; gap: 5px; }}
        #search-input {{ flex: 1; padding: 12px 15px; border: 2px solid #4CAF50; border-radius: 8px; font-size: 16px; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
        #search-btn, #location-btn {{ padding: 12px 20px; background: #4CAF50; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
        #search-btn:hover, #location-btn:hover {{ background: #45a049; }}
        .custom-overlay {{ position: relative; background: white; border: 2px solid #4CAF50; border-radius: 8px; padding: 10px 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.3); max-width: 250px; }}
        .overlay-title {{ font-weight: bold; font-size: 14px; color: #333; margin-bottom: 5px; }}
        .overlay-address {{ font-size: 12px; color: #666; margin-bottom: 3px; }}
        .overlay-phone {{ font-size: 12px; color: #4CAF50; }}
        .overlay-close {{ position: absolute; top: 5px; right: 8px; cursor: pointer; font-size: 18px; color: #999; }}
    </style>
</head>
<body>
    <div id="search-container">
        <input type="text" id="search-input" placeholder="약국 이름 또는 주소 검색">
        <button id="search-btn">검색</button>
        <button id="location-btn">📍</button>
    </div>
    <div id="map"></div>
    <script>
        kakao.maps.load(function() {{
        var map = new kakao.maps.Map(document.getElementById('map'), {{ center: new kakao.maps.LatLng(37.5665, 126.9780), level: 3 }});
        var ps = new kakao.maps.services.Places();
        var markers = [];
        var customOverlays = [];

        document.getElementById('search-btn').addEventListener('click', function() {{
            var keyword = document.getElementById('search-input').value;
            if (!keyword.trim()) {{ alert('검색어를 입력해주세요'); return; }}
            ps.keywordSearch(keyword + ' 약국', placesSearchCB);
        }});

        document.getElementById('search-input').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') document.getElementById('search-btn').click();
        }});

        document.getElementById('location-btn').addEventListener('click', function() {{
            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition(function(position) {{
                    var lat = position.coords.latitude, lng = position.coords.longitude;
                    var locPosition = new kakao.maps.LatLng(lat, lng);
                    map.setCenter(locPosition);
                    var marker = new kakao.maps.Marker({{ map: map, position: locPosition }});
                    new kakao.maps.InfoWindow({{ content: '<div style="padding:5px;">현재 위치</div>' }}).open(map, marker);
                    ps.keywordSearch('약국', placesSearchCB, {{ location: locPosition, radius: 1000, sort: kakao.maps.services.SortBy.DISTANCE }});
        }});
            }} else {{ alert('GPS를 지원하지 않는 브라우저입니다'); }}
        }});

        function placesSearchCB(data, status) {{
            if (status === kakao.maps.services.Status.OK) {{ clearMarkers(); displayPlaces(data); }}
            else if (status === kakao.maps.services.Status.ZERO_RESULT) {{ alert('검색 결과가 없습니다'); }}
            else if (status === kakao.maps.services.Status.ERROR) {{ alert('검색 중 오류가 발생했습니다'); }}
        }}

        function displayPlaces(places) {{
            var bounds = new kakao.maps.LatLngBounds();
            for (var i = 0; i < places.length; i++) {{
                var pos = new kakao.maps.LatLng(places[i].y, places[i].x);
                var marker = addMarker(pos, i);
                bounds.extend(pos);
                (function(m, p) {{ kakao.maps.event.addListener(m, 'click', function() {{ displayInfowindow(m, p); }}); }})(marker, places[i]);
            }}
            map.setBounds(bounds);
        }}

        function addMarker(position, idx) {{
            var marker = new kakao.maps.Marker({{
                position: position,
                image: new kakao.maps.MarkerImage('https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_number_blue.png',
                    new kakao.maps.Size(36, 37), {{ spriteSize: new kakao.maps.Size(36, 691), spriteOrigin: new kakao.maps.Point(0, idx*46+10), offset: new kakao.maps.Point(13, 37) }})
        }});
            marker.setMap(map);
            markers.push(marker);
            return marker;
        }}

        function displayInfowindow(marker, place) {{
            clearCustomOverlays();
            var content = '<div class="custom-overlay"><span class="overlay-close" onclick="clearCustomOverlays()">✕</span>' +
                '<div class="overlay-title">' + place.place_name + '</div>' +
                '<div class="overlay-address">' + (place.road_address_name || place.address_name) + '</div>' +
                '<div class="overlay-phone">' + (place.phone || '전화번호 없음') + '</div></div>';
            var overlay = new kakao.maps.CustomOverlay({{ map: map, position: marker.getPosition(), content: content, yAnchor: 1.5 }});
            customOverlays.push(overlay);
        }}

        function clearMarkers() {{ markers.forEach(m => m.setMap(null)); markers = []; clearCustomOverlays(); }}
        function clearCustomOverlays() {{ customOverlays.forEach(o => o.setMap(null)); customOverlays = []; }}

        document.getElementById('location-btn').click();
        }});
    </script>
</body>
</html>
    '''
    return HttpResponse(html_content, content_type='text/html; charset=utf-8')
