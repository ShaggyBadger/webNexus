import logging
import json
import urllib.request
from urllib.error import URLError
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from ..models import FuelRack
from tankgauge.models import Store, TankType
from tankgauge.logic.utils import haversine
from ..logic import rack_ops

# Configure Tactical Logger for Site Intelligence
logger = logging.getLogger('webnexus')

@login_required
def reverse_geocode_api(request):
    """
    TACTICAL INTEL:
    Reverse geocoding using Nominatim (OpenStreetMap).
    Converts LAT/LON coordinates into a physical address to reduce manual entry errors.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        logger.warning("GEOCODE_ATTEMPT_FAILED: Missing coordinates in request.")
        return JsonResponse({'error': 'LAT and LON are required'}, status=400)
    
    logger.info(f"GEOCODE_REQUEST: Lat {lat}, Lon {lon} triggered by user {request.user}")
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'webNexus-Tactical-Agent/1.0'}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
            address = data.get('address', {})
            # Tactical normalization of address components
            result = {
                'address': address.get('house_number', '') + ' ' + address.get('road', '') if address.get('road') else address.get('pedestrian', ''),
                'city': address.get('city') or address.get('town') or address.get('village') or address.get('suburb', ''),
                'state': address.get('state', ''),
                'zip_code': address.get('postcode', '')
            }
            logger.info(f"GEOCODE_SUCCESS: Decoded to {result.get('address')}, {result.get('city')}")
            return JsonResponse(result)
            
    except URLError as e:
        logger.error(f"GEOCODE_SERVICE_UNAVAILABLE: {str(e)}")
        return JsonResponse({'error': 'Service unavailable'}, status=503)
    except Exception as e:
        logger.error(f"GEOCODE_UNEXPECTED_FAILURE: {str(e)}")
        return JsonResponse({'error': 'Internal error'}, status=500)

@login_required
def proximity_check_api(request):
    """
    TACTICAL INTEL:
    Checks for existing stores within a ~250ft (0.05 mile) radius.
    Used as a duplication safeguard during new site proposals.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    exclude_num = request.GET.get('exclude_store_num')
    
    if not lat or not lon:
        logger.warning("PROXIMITY_CHECK_ABORTED: Missing coordinates.")
        return JsonResponse({'error': 'LAT and LON are required'}, status=400)
    
    try:
        lat_val = float(lat)
        lon_val = float(lon)
    except ValueError:
        logger.warning(f"PROXIMITY_CHECK_FAILED: Invalid coordinates provided: {lat}, {lon}")
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)
        
    # Search radius in miles (0.05 miles is approx 264 feet)
    RADIUS = 0.05
    
    matches = []
    stores = Store.objects.exclude(lat__isnull=True).exclude(lon__isnull=True)
    
    if exclude_num:
        stores = stores.exclude(store_num=exclude_num)
        
    for store in stores:
        dist = haversine(lat_val, lon_val, store.lat, store.lon)
        if dist <= RADIUS:
            matches.append({
                'store_num': store.store_num,
                'store_name': store.store_name,
                'distance_ft': int(dist * 5280) # Convert miles to feet
            })
    
    if matches:
        logger.warning(f"PROXIMITY_ALERT: {len(matches)} sites detected near Lat {lat}, Lon {lon} by user {request.user}")
    else:
        logger.info(f"PROXIMITY_CLEARED: No conflicting sites detected for Lat {lat}, Lon {lon}")
            
    return JsonResponse({'matches': matches})

@login_required
def rack_status_api(request):
    """
    TACTICAL INTEL:
    Returns the lockout status for fuel racks relative to the current user.
    Can be filtered by a specific rack_id.
    """
    rack_id = request.GET.get('rack_id')
    
    if rack_id:
        rack = get_object_or_404(FuelRack, id=rack_id)
        status = rack_ops.get_rack_status(request.user, rack)
        return JsonResponse({
            'rack_id': rack.id,
            'name': rack.location.name,
            'status': status
        })
    
    # Return all racks with user status
    racks = FuelRack.objects.all().select_related('location')
    results = []
    for rack in racks:
        status = rack_ops.get_rack_status(request.user, rack)
        results.append({
            'id': rack.id,
            'name': rack.location.name,
            'lat': rack.location.lat,
            'lon': rack.location.lon,
            'status': status
        })
        
    return JsonResponse({'racks': results})

@login_required
def rack_checkin_api(request):
    """
    TACTICAL INTEL:
    POST endpoint to record a fuel rack check-in.
    Resets the lockout timer for the user.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    try:
        data = json.loads(request.body)
        rack_id = data.get('rack_id')
        lat = data.get('lat')
        lon = data.get('lon')
        accuracy = data.get('accuracy')
        
        if not rack_id:
            return JsonResponse({'error': 'rack_id is required'}, status=400)
            
        rack = get_object_or_404(FuelRack, id=rack_id)
        checkin = rack_ops.record_checkin(
            user=request.user,
            rack=rack,
            lat=float(lat) if lat is not None else None,
            lon=float(lon) if lon is not None else None,
            accuracy=float(accuracy) if accuracy is not None else None
        )
        
        status = rack_ops.get_rack_status(request.user, rack)
        
        return JsonResponse({
            'success': True,
            'message': f"Check-in recorded at {rack.location.name}",
            'is_verified': checkin.is_verified,
            'status': status
        })
        
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"RACK_CHECKIN_ERROR: Invalid data - {str(e)}")
        return JsonResponse({'error': 'Invalid request data'}, status=400)
    except Exception as e:
        logger.error(f"RACK_CHECKIN_CRITICAL: {str(e)}")
        return JsonResponse({'error': 'Server error'}, status=500)

@login_required
def tank_type_search_api(request):
    """
    TACTICAL INTEL:
    AJAX endpoint for the 'Tank Picker'.
    Queries TankType records within a +/- 10% tolerance of the reported capacity.
    """
    capacity = request.GET.get('capacity')
    query = request.GET.get('q')
    
    if not capacity and not query:
        return JsonResponse({'error': 'Capacity or Query is required'}, status=400)
    
    filters = Q()
    
    if capacity:
        try:
            cap_val = int(capacity)
            lower_bound = cap_val * 0.9
            upper_bound = cap_val * 1.1
            filters &= Q(capacity__gte=lower_bound, capacity__lte=upper_bound)
            logger.info(f"TANK_SEARCH: Capacity near {cap_val}G for {request.user}")
        except ValueError:
            logger.warning(f"TANK_SEARCH_FAILED: Invalid capacity '{capacity}'")
            
    if query:
        filters &= (Q(name__icontains=query) | Q(manufacturer__icontains=query) | Q(model__icontains=query))
    
    matches = TankType.objects.filter(filters).values('id', 'name', 'manufacturer', 'capacity', 'max_depth')[:20]
    return JsonResponse({'results': list(matches)})

@login_required
def store_lookup_api(request):
    """
    TACTICAL INTEL:
    AJAX endpoint for pre-filling the proposal form if a store is identified.
    Returns store metadata and canonical tank mappings.
    """
    query = request.GET.get('q')
    if not query:
        return JsonResponse({'error': 'Query is required'}, status=400)
    
    logger.info(f"STORE_LOOKUP_REQUEST: ID '{query}' triggered by {request.user}")
    store = Store.objects.filter(
        Q(store_num=query) | Q(riso_num=query)
    ).first()
    
    if store:
        logger.info(f"STORE_LOOKUP_HIT: Found Store #{store.store_num}")
        from tankgauge.models import StoreTankMapping
        mappings = StoreTankMapping.objects.filter(store=store).order_by('tank_index')
        tanks = []
        for m in mappings:
            tanks.append({
                'tank_index': m.tank_index,
                'fuel_type': m.fuel_type,
                'capacity': m.tank_type.capacity if m.tank_type else 0,
                'max_depth': m.tank_type.max_depth if m.tank_type else 0,
                'tank_type_id': m.tank_type.id if m.tank_type else None,
                'tank_type_name': m.tank_type.name if m.tank_type else 'UNKNOWN'
            })

        data = {
            'store_num': store.store_num,
            'riso_num': store.riso_num,
            'store_name': store.store_name,
            'store_type': store.store_type,
            'address': store.address,
            'city': store.city,
            'state': store.state,
            'zip_code': store.zip_code,
            'lat': store.lat,
            'lon': store.lon,
            'tanks': tanks
        }
        return JsonResponse(data)
    
    logger.info(f"STORE_LOOKUP_MISS: No record found for ID '{query}'")
    return JsonResponse({'error': 'Store not found'}, status=404)

def site_lookup_api(request):
    """
    TACTICAL INTEL:
    Numeric-focused lookup for site selection.
    Targets Store Numbers and RISO identifiers. 
    Optimized for high-speed target acquisition in field conditions.
    """
    q = request.GET.get('q', '').strip()
    if not q or not q.isdigit():
        return JsonResponse({'results': []})
    
    user_str = request.user.username if request.user.is_authenticated else "ANONYMOUS"
    logger.info(f"TARGET_SCAN: Searching for site ID '{q}' by user {user_str}")
    
    # SEARCH_STORES: Target canonical retail sites by ID
    stores = Store.objects.filter(
        Q(store_num__icontains=q) | Q(riso_num__icontains=q)
    ).select_related('location')[:10]
    
    results = []
    for s in stores:
        loc_id = s.location.id if s.location else None
        results.append({
            'type': 'STORE',
            'id': loc_id,
            'store_pk': s.id,
            'store_num': s.store_num,
            'name': s.store_name or f"Store #{s.store_num}",
            'city': s.city or "UNKNOWN LOC",
            'has_location': loc_id is not None
        })
    
    logger.info(f"TARGET_SCAN_COMPLETE: Identified {len(results)} potential targets for ID '{q}'")
    return JsonResponse({'results': results})
