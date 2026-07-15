# apps/hotel_master/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.db.models import Sum, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Room, Booking
from django.views.decorators.csrf import csrf_exempt
import json
from apps.shared.utils.project_helpers import get_project_template_dir
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta

# ============================================
# HELPER: Get the correct template path
# ============================================

def get_template_path(template_name, tenant):
    """
    Get the correct template path based on tenant's project type.
    If tenant has HOTEL_MASTER -> uses hotel_master/template_name
    If tenant has TRONIC_MASTER -> uses tronic_master/template_name
    """
    if tenant:
        project_type = getattr(tenant, 'project_type', None)
        if project_type:
            project_code = project_type.code.upper()
            template_dir = get_project_template_dir(project_code)
            return f"{template_dir}/{template_name}"
    
    # Default to hotel_master if no tenant or project type
    return f"hotel_master/{template_name}"


# ============================================
# HOTEL MASTER DASHBOARD VIEWS
# ============================================

@login_required
def dashboard(request):
    """HOTEL MASTER Dashboard"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get statistics
    total_rooms = Room.objects.filter(tenant=tenant).count()
    available_rooms = Room.objects.filter(tenant=tenant, status='available').count()
    occupied_rooms = Room.objects.filter(tenant=tenant, status='occupied').count()
    
    # Today's bookings
    today = timezone.now().date()
    today_bookings = Booking.objects.filter(
        tenant=tenant,
        check_in=today
    ).count()
    
    # Occupancy rate
    occupancy_rate = 0
    if total_rooms > 0:
        occupancy_rate = int(((total_rooms - available_rooms) / total_rooms) * 100)
    
    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied_rooms': occupied_rooms,
        'today_bookings': today_bookings,
        'occupancy_rate': occupancy_rate,
    }
    
    # ✅ Use dynamic template path
    template_path = get_template_path('dashboard_hotel.html', tenant)
    return render(request, template_path, context)

@login_required
def pos(request):
    """Hotel Master POS - Coming Soon"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('hotel_master:dashboard')
    
    context = {
        'tenant': tenant,
        'active_tab': 'pos',
    }
    template_path = get_template_path('pos.html', tenant) 
    return render(request, 'hotel_master/pos.html', context)

@login_required
def rooms(request):
    """Hotel Rooms"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    rooms_list = Room.objects.filter(tenant=tenant)
    
    # Statistics
    total_rooms = rooms_list.count()
    available_rooms = rooms_list.filter(status='available').count()
    occupied_rooms = rooms_list.filter(status='occupied').count()
    reserved_rooms = rooms_list.filter(status='reserved').count()
    maintenance_rooms = rooms_list.filter(status='maintenance').count()
    
    occupancy_rate = 0
    if total_rooms > 0:
        occupancy_rate = int(((total_rooms - available_rooms) / total_rooms) * 100)
    
    context = {
        'tenant': tenant,
        'rooms': rooms_list,
        'active_tab': 'rooms',
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied_rooms': occupied_rooms,
        'reserved_rooms': reserved_rooms,
        'maintenance_rooms': maintenance_rooms,
        'occupancy_rate': occupancy_rate,
    }
    template_path = get_template_path('rooms.html', tenant)  # ✅
    return render(request, 'hotel_master/rooms.html', context)

@login_required
def room_status(request):
    """Room Status - View all rooms and their current status"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get all rooms for this tenant
    rooms = Room.objects.filter(tenant=tenant).order_by('room_number')
    
    # Get statistics
    total_rooms = rooms.count()
    available_rooms = rooms.filter(status='available').count()
    occupied_rooms = rooms.filter(status='occupied').count()
    reserved_rooms = rooms.filter(status='reserved').count()
    maintenance_rooms = rooms.filter(status='maintenance').count()
    
    # Calculate occupancy rate
    occupancy_rate = 0
    if total_rooms > 0:
        occupied_total = occupied_rooms + reserved_rooms
        occupancy_rate = int((occupied_total / total_rooms) * 100)
    
    # Get current bookings for occupied/reserved rooms
    current_bookings = {}
    booked_rooms = rooms.filter(status__in=['occupied', 'reserved'])
    for room in booked_rooms:
        booking = Booking.objects.filter(
            tenant=tenant,
            room=room,
            status__in=['confirmed', 'checked_in']
        ).order_by('-created_at').first()
        if booking:
            current_bookings[room.id] = {
                'guest_name': booking.guest_name,
                'check_in': booking.check_in,
                'check_out': booking.check_out,
                'booking_number': booking.booking_number,
            }
    
    context = {
        'tenant': tenant,
        'rooms': rooms,
        'current_bookings': current_bookings,
        'active_tab': 'rooms',
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'occupied_rooms': occupied_rooms,
        'reserved_rooms': reserved_rooms,
        'maintenance_rooms': maintenance_rooms,
        'occupancy_rate': occupancy_rate,
    }
    template_path = get_template_path('room_status.html', tenant)
    return render(request, template_path, context)

@login_required
def add_room(request):
    """Add Room"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    if request.method == 'POST':
        room_number = request.POST.get('room_number')
        room_type = request.POST.get('room_type')
        floor = request.POST.get('floor', 1)
        capacity = request.POST.get('capacity', 2)
        price = request.POST.get('price', 0)
        
        # Features
        has_ac = request.POST.get('has_ac') == 'on'
        has_tv = request.POST.get('has_tv') == 'on'
        has_wifi = request.POST.get('has_wifi') == 'on'
        has_minibar = request.POST.get('has_minibar') == 'on'
        has_bathroom = request.POST.get('has_bathroom') == 'on'
        has_balcony = request.POST.get('has_balcony') == 'on'
        has_kitchenette = request.POST.get('has_kitchenette') == 'on'
        has_safe = request.POST.get('has_safe') == 'on'
        has_iron = request.POST.get('has_iron') == 'on'
        has_hairdryer = request.POST.get('has_hairdryer') == 'on'
        has_phone = request.POST.get('has_phone') == 'on'
        has_smoking = request.POST.get('has_smoking') == 'on'
        
        description = request.POST.get('description', '')
        
        if not room_number or not room_type:
            messages.error(request, 'Room number and type are required.')
            return redirect('hotel_master:add_room')
        
        # Check if room number already exists
        if Room.objects.filter(tenant=tenant, room_number=room_number).exists():
            messages.error(request, f'Room {room_number} already exists.')
            return redirect('hotel_master:add_room')
        
        try:
            room = Room.objects.create(
                tenant=tenant,
                room_number=room_number,
                room_type=room_type,
                floor=floor,
                capacity=capacity,
                price=price,
                has_ac=has_ac,
                has_tv=has_tv,
                has_wifi=has_wifi,
                has_minibar=has_minibar,
                has_bathroom=has_bathroom,
                has_balcony=has_balcony,
                has_kitchenette=has_kitchenette,
                has_safe=has_safe,
                has_iron=has_iron,
                has_hairdryer=has_hairdryer,
                has_phone=has_phone,
                has_smoking=has_smoking,
                description=description,
            )
            messages.success(request, f'Room {room.room_number} added successfully!')
            return redirect('hotel_master:rooms')
        except Exception as e:
            messages.error(request, f'Error adding room: {str(e)}')
            return redirect('hotel_master:add_room')
    
    context = {'tenant': tenant}
    return render(request, 'hotel_master/add_room.html', context)

@login_required
def edit_room_view(request, room_id):
    """Edit room view (fallback for non-JS)"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('hotel_master:dashboard')
    
    try:
        room = Room.objects.get(id=room_id, tenant=tenant)
    except Room.DoesNotExist:
        messages.error(request, 'Room not found')
        return redirect('hotel_master:rooms')
    
    if request.method == 'POST':
        # Similar to API edit but with redirect
        room.room_number = request.POST.get('room_number', room.room_number)
        room.room_type = request.POST.get('room_type', room.room_type)
        room.floor = request.POST.get('floor', room.floor)
        room.capacity = request.POST.get('capacity', room.capacity)
        room.price = request.POST.get('price', room.price)
        room.status = request.POST.get('status', room.status)
        room.description = request.POST.get('description', room.description)
        
        # Features...
        room.save()
        messages.success(request, 'Room updated successfully!')
        return redirect('hotel_master:rooms')
    
    context = {
        'tenant': tenant,
        'room': room,
        'active_tab': 'rooms',
    }
    return render(request, 'hotel_master/edit_room.html', context)

@login_required
def bookings(request):
    """Hotel Bookings"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    bookings_list = Booking.objects.filter(tenant=tenant).select_related('room')
    
    total_bookings = bookings_list.count()
    confirmed_bookings = bookings_list.filter(status='confirmed').count()
    checked_in_bookings = bookings_list.filter(status='checked_in').count()
    total_revenue = bookings_list.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Pagination
    paginator = Paginator(bookings_list, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'bookings': page_obj,
        'active_tab': 'bookings',
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'checked_in_bookings': checked_in_bookings,
        'total_revenue': total_revenue,
    }
    return render(request, 'hotel_master/bookings.html', context)

@login_required
def new_booking(request):
    """New Booking"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    available_rooms = Room.objects.filter(tenant=tenant, status='available')
    
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        guest_name = request.POST.get('guest_name')
        guest_phone = request.POST.get('guest_phone')
        guest_email = request.POST.get('guest_email')
        guest_id = request.POST.get('guest_id')
        guest_address = request.POST.get('guest_address')
        check_in = request.POST.get('check_in')
        check_out = request.POST.get('check_out')
        guests = request.POST.get('guests', 1)
        booking_type = request.POST.get('booking_type', 'standard')
        special_requests = request.POST.get('special_requests', '')
        total_amount = request.POST.get('total_amount', 0)
        payment_method = request.POST.get('payment_method', 'cash')
        payment_status = request.POST.get('payment_status', 'pending')
        notes = request.POST.get('notes', '')
        
        if not room_id or not guest_name or not guest_phone or not check_in or not check_out:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('hotel_master:new_booking')
        
        try:
            room = Room.objects.get(id=room_id, tenant=tenant)
            
            # Check if room is available
            if room.status != 'available':
                messages.error(request, 'Selected room is not available.')
                return redirect('hotel_master:new_booking')
            
            booking = Booking.objects.create(
                tenant=tenant,
                room=room,
                guest_name=guest_name,
                guest_phone=guest_phone,
                guest_email=guest_email,
                guest_id_number=guest_id,
                guest_address=guest_address,
                check_in=check_in,
                check_out=check_out,
                number_of_guests=guests,
                booking_type=booking_type,
                special_requests=special_requests,
                total_amount=total_amount,
                paid_amount=total_amount if payment_status == 'paid' else 0,
                payment_method=payment_method,
                payment_status=payment_status,
                status='confirmed' if payment_status == 'paid' else 'pending',
                notes=notes,
                created_by=request.user
            )
            
            # Update room status
            room.status = 'reserved'
            room.save()
            
            messages.success(request, f'Booking {booking.booking_number} created successfully!')
            return redirect('hotel_master:bookings')
            
        except Room.DoesNotExist:
            messages.error(request, 'Selected room not found.')
            return redirect('hotel_master:new_booking')
        except Exception as e:
            messages.error(request, f'Error creating booking: {str(e)}')
            return redirect('hotel_master:new_booking')
    
    context = {
        'tenant': tenant,
        'available_rooms': available_rooms,
        'today': timezone.now().date(),
        'active_tab': 'bookings',
    }
    return render(request, 'hotel_master/new_booking.html', context)

@login_required
def guests(request):
    """Hotel Guests"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get all bookings (guests) for this tenant
    guests_list = Booking.objects.filter(
        tenant=tenant
    ).select_related('room').order_by('-created_at')
    
    # Statistics
    total_guests = guests_list.count()
    checked_in_guests = guests_list.filter(status='checked_in').count()
    checked_out_guests = guests_list.filter(status='checked_out').count()
    
    # Today's check-ins
    today = timezone.now().date()
    today_checkins = guests_list.filter(check_in=today).count()
    
    # Pagination
    paginator = Paginator(guests_list, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'guests': page_obj,
        'active_tab': 'guests',
        'total_guests': total_guests,
        'checked_in_guests': checked_in_guests,
        'checked_out_guests': checked_out_guests,
        'today_checkins': today_checkins,
    }
    return render(request, 'hotel_master/guests.html', context)

@login_required
def checkin(request):
    """Check In"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get confirmed bookings not yet checked in
    pending_checkins = Booking.objects.filter(
        tenant=tenant,
        status='confirmed'
    ).select_related('room').order_by('check_in')
    
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        checkin_time = request.POST.get('checkin_time')
        payment_status = request.POST.get('payment_status', 'paid')
        id_verified = request.POST.get('id_verified', 'yes')
        checkin_notes = request.POST.get('checkin_notes', '')
        
        try:
            booking = Booking.objects.get(id=booking_id, tenant=tenant)
            
            # Update booking status
            booking.status = 'checked_in'
            booking.payment_status = payment_status
            booking.notes = checkin_notes
            booking.save()
            
            # Update room status
            room = booking.room
            room.status = 'occupied'
            room.save()
            
            messages.success(request, f'Guest {booking.guest_name} checked in successfully!')
            return redirect('hotel_master:checkin')
            
        except Booking.DoesNotExist:
            messages.error(request, 'Booking not found')
            return redirect('hotel_master:checkin')
        except Exception as e:
            messages.error(request, f'Error during check in: {str(e)}')
            return redirect('hotel_master:checkin')
    
    context = {
        'tenant': tenant,
        'pending_checkins': pending_checkins,
        'active_tab': 'checkin',
    }
    return render(request, 'hotel_master/checkin.html', context)

@login_required
def quick_checkin(request):
    """Quick Check In - For walk-in guests without prior booking"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get all available rooms
    available_rooms = Room.objects.filter(tenant=tenant, status='available')
    
    if request.method == 'POST':
        # Process quick check-in
        room_id = request.POST.get('room_id')
        guest_name = request.POST.get('guest_name')
        guest_phone = request.POST.get('guest_phone')
        guest_email = request.POST.get('guest_email')
        guest_id = request.POST.get('guest_id_number')
        guest_address = request.POST.get('guest_address')
        check_out = request.POST.get('check_out')
        number_of_guests = request.POST.get('number_of_guests', 1)
        payment_method = request.POST.get('payment_method', 'cash')
        amount_paid = request.POST.get('amount_paid', 0)
        
        # Validate required fields
        if not room_id or not guest_name or not guest_phone or not check_out:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('hotel_master:quick_checkin')
        
        try:
            room = Room.objects.get(id=room_id, tenant=tenant)
            
            # Check if room is available
            if room.status != 'available':
                messages.error(request, f'Room {room.room_number} is not available.')
                return redirect('hotel_master:quick_checkin')
            
            # Calculate total amount (assuming check-in is today)
            from datetime import datetime
            check_in = timezone.now().date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            nights = (check_out_date - check_in).days
            
            if nights <= 0:
                messages.error(request, 'Check-out date must be after today.')
                return redirect('hotel_master:quick_checkin')
            
            total_amount = float(room.price) * nights
            
            # Generate booking number
            import random
            booking_number = f"BK-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            
            # Create booking
            booking = Booking.objects.create(
                tenant=tenant,
                room=room,
                booking_number=booking_number,
                guest_name=guest_name,
                guest_phone=guest_phone,
                guest_email=guest_email or '',
                guest_id_number=guest_id or '',
                guest_address=guest_address or '',
                check_in=check_in,
                check_out=check_out_date,
                number_of_guests=number_of_guests,
                booking_type='walk_in',
                total_amount=total_amount,
                paid_amount=float(amount_paid) if amount_paid else 0,
                payment_method=payment_method,
                payment_status='paid' if float(amount_paid) >= total_amount else 'pending',
                status='checked_in',  # Direct check-in for walk-in guests
                created_by=request.user
            )
            
            # Update room status
            room.status = 'occupied'
            room.save()
            
            messages.success(request, f'Guest {guest_name} checked in to Room {room.room_number} successfully!')
            return redirect('hotel_master:checkin')
            
        except Room.DoesNotExist:
            messages.error(request, 'Selected room not found.')
            return redirect('hotel_master:quick_checkin')
        except Exception as e:
            messages.error(request, f'Error during check-in: {str(e)}')
            return redirect('hotel_master:quick_checkin')
    
    context = {
        'tenant': tenant,
        'available_rooms': available_rooms,
        'today': timezone.now().date(),
        'active_tab': 'checkin',
    }
    template_path = get_template_path('quick_checkin.html', tenant)
    return render(request, template_path, context)

@login_required
def checkout(request):
    """Check Out"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get checked in bookings
    checked_in_bookings = Booking.objects.filter(
        tenant=tenant,
        status='checked_in'
    ).select_related('room').order_by('check_in')
    
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        final_amount = request.POST.get('final_amount')
        checkout_notes = request.POST.get('checkout_notes', '')
        
        try:
            booking = Booking.objects.get(id=booking_id, tenant=tenant)
            
            # Update booking
            booking.status = 'checked_out'
            booking.total_amount = final_amount
            booking.notes = checkout_notes
            booking.save()
            
            # Update room status
            room = booking.room
            room.status = 'available'
            room.save()
            
            messages.success(request, f'Guest {booking.guest_name} checked out successfully!')
            return redirect('hotel_master:checkout')
            
        except Booking.DoesNotExist:
            messages.error(request, 'Booking not found')
            return redirect('hotel_master:checkout')
        except Exception as e:
            messages.error(request, f'Error during check out: {str(e)}')
            return redirect('hotel_master:checkout')
    
    context = {
        'tenant': tenant,
        'checked_in_bookings': checked_in_bookings,
        'active_tab': 'checkout',
    }
    return render(request, 'hotel_master/checkout.html', context)


# ============================================
# API VIEWS
# ============================================

@login_required
def api_booking_detail(request, booking_id):
    """API endpoint for booking details"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        booking = Booking.objects.get(id=booking_id, tenant=tenant)
        
        # Calculate nights
        nights = (booking.check_out - booking.check_in).days if booking.check_in and booking.check_out else 1
        
        # Status display mapping (in case model doesn't have get_status_display)
        status_display_map = {
            'confirmed': 'Confirmed',
            'pending': 'Pending',
            'checked_in': 'Checked In',
            'checked_out': 'Checked Out',
            'cancelled': 'Cancelled',
            'no_show': 'No Show',
        }
        
        # Try to use model's get_status_display, fallback to mapping
        try:
            status_display = booking.get_status_display()
        except AttributeError:
            status_display = status_display_map.get(booking.status, booking.status.title())
        
        data = {
            'success': True,
            'booking': {
                'id': booking.id,
                'booking_number': booking.booking_number,
                'guest_name': booking.guest_name,
                'guest_phone': booking.guest_phone,
                'guest_email': booking.guest_email or '',
                'guest_id': booking.guest_id_number or '',
                'check_in': booking.check_in.strftime('%Y-%m-%d'),
                'check_out': booking.check_out.strftime('%Y-%m-%d'),
                'room_number': booking.room.room_number,
                'room_price': float(booking.room.price),
                'guests': booking.number_of_guests,
                'total_amount': float(booking.total_amount or 0),
                'paid_amount': float(booking.paid_amount or 0),
                'payment_status': booking.payment_status or 'pending',
                'status': booking.status,
                'status_display': status_display,
                'special_requests': booking.special_requests or '',
                'notes': booking.notes or '',
                'nights': nights,
            }
        }
        return JsonResponse(data)
        
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Booking not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_rooms(request):
    """API endpoint for rooms"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    query = request.GET.get('q', '')
    rooms = Room.objects.filter(tenant=tenant)
    
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query) |
            Q(room_type__icontains=query)
        )
    
    # Only show available rooms for POS
    rooms = rooms.filter(status='available')
    
    data = []
    for room in rooms[:20]:
        data.append({
            'id': room.id,
            'room_number': room.room_number,
            'room_type': room.get_room_type_display(),
            'floor': room.floor,
            'price': float(room.price),
            'status': room.status,
        })
    
    return JsonResponse({'rooms': data})


@login_required
def api_search_customer(request):
    """API endpoint for customer search"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    phone = request.GET.get('phone', '')
    if not phone:
        return JsonResponse({'error': 'Phone number required'}, status=400)
    
    # Search in bookings for guests
    booking = Booking.objects.filter(
        tenant=tenant,
        guest_phone=phone
    ).order_by('-created_at').first()
    
    if booking:
        return JsonResponse({
            'success': True,
            'found': True,
            'customer': {
                'name': booking.guest_name,
                'phone': booking.guest_phone,
                'email': booking.guest_email,
                'id': booking.guest_id_number,
            }
        })
    
    return JsonResponse({'success': True, 'found': False})


@login_required
@csrf_exempt
def api_process_payment(request):
    """API endpoint for processing payment"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        total = data.get('total', 0)
        payment_method = data.get('payment_method', 'cash')
        amount_paid = data.get('amount_paid', 0)
        room_id = data.get('room_id')
        customer_data = data.get('customer')
        
        if not items:
            return JsonResponse({'error': 'Cart is empty'}, status=400)
        
        # Create booking/invoice
        import random
        import datetime
        invoice_number = f"INV-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        # Get room if assigned
        room = None
        if room_id:
            try:
                room = Room.objects.get(id=room_id, tenant=tenant)
            except Room.DoesNotExist:
                pass
        
        # Create sale record (you may want to create a proper Sale model)
        # For now, we'll return success
        
        return JsonResponse({
            'success': True,
            'sale_id': random.randint(1000, 9999),
            'invoice_number': invoice_number,
            'total': total,
            'amount_paid': amount_paid,
            'change': amount_paid - total,
            'room_number': room.room_number if room else 'Walk-in',
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_assign_guest(request):
    """API endpoint for assigning a guest to a room"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    try:
        data = json.loads(request.body)
        
        # Extract data
        room_id = data.get('room_id')
        guest_name = data.get('guest_name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        id_number = data.get('id_number', '').strip()
        checkin_date = data.get('checkin_date')
        checkout_date = data.get('checkout_date')
        guest_count = data.get('guest_count', 1)
        extras = data.get('extras', {})
        special_requests = data.get('special_requests', '').strip()
        
        # Validate required fields
        if not room_id:
            return JsonResponse({'success': False, 'error': 'Room is required'}, status=400)
        
        if not guest_name:
            return JsonResponse({'success': False, 'error': 'Guest name is required'}, status=400)
        
        if not phone:
            return JsonResponse({'success': False, 'error': 'Phone number is required'}, status=400)
        
        if not checkin_date or not checkout_date:
            return JsonResponse({'success': False, 'error': 'Check-in and check-out dates are required'}, status=400)
        
        # Get room
        try:
            room = Room.objects.get(id=room_id, tenant=tenant)
        except Room.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Room not found'}, status=404)
        
        # Check if room is available
        if room.status != 'available':
            return JsonResponse({'success': False, 'error': f'Room {room.room_number} is not available'}, status=400)
        
        # Calculate total amount
        from datetime import datetime
        checkin = datetime.strptime(checkin_date, '%Y-%m-%d').date()
        checkout = datetime.strptime(checkout_date, '%Y-%m-%d').date()
        nights = (checkout - checkin).days
        
        if nights <= 0:
            return JsonResponse({'success': False, 'error': 'Check-out must be after check-in'}, status=400)
        
        # Base price
        total_amount = float(room.price) * nights
        
        # Add extras
        extra_charges = 0
        extra_details = []
        
        if extras.get('breakfast'):
            extra_charges += 500 * guest_count * nights
            extra_details.append(f'Breakfast (KES 500 x {guest_count} guests x {nights} nights)')
        
        if extras.get('parking'):
            extra_charges += 300 * nights
            extra_details.append(f'Parking (KES 300 x {nights} nights)')
        
        if extras.get('late_checkout'):
            extra_charges += 1000
            extra_details.append('Late Check-out (KES 1,000)')
        
        total_amount += extra_charges
        
        # Create booking
        import random
        import datetime as dt
        booking_number = f"BK-{dt.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        booking = Booking.objects.create(
            tenant=tenant,
            room=room,
            booking_number=booking_number,
            guest_name=guest_name,
            guest_phone=phone,
            guest_email=email or '',
            guest_id_number=id_number or '',
            check_in=checkin,
            check_out=checkout,
            number_of_guests=guest_count,
            total_amount=total_amount,
            paid_amount=0,  # Payment will be collected at check-in
            payment_status='pending',
            status='confirmed',
            special_requests=special_requests,
            notes=f"Extras: {', '.join(extra_details)}" if extra_details else '',
            created_by=request.user
        )
        
        # Update room status
        room.status = 'reserved'
        room.save()
        
        # Return success response
        return JsonResponse({
            'success': True,
            'booking_id': booking.id,
            'booking_number': booking.booking_number,
            'guest_name': booking.guest_name,
            'room_number': room.room_number,
            'checkin_date': checkin_date,
            'checkout_date': checkout_date,
            'total_amount': total_amount,
            'nights': nights,
            'extras': extra_details,
            'message': f'Guest {guest_name} assigned to Room {room.room_number} successfully!'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@login_required
def api_room_detail(request, room_id):
    """API endpoint for room details"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        room = Room.objects.get(id=room_id, tenant=tenant)
        
        # Get current booking if any
        current_booking = None
        if room.status in ['occupied', 'reserved']:
            booking = Booking.objects.filter(
                room=room,
                status__in=['confirmed', 'checked_in']
            ).first()
            if booking:
                current_booking = {
                    'guest_name': booking.guest_name,
                    'check_in': booking.check_in.strftime('%Y-%m-%d'),
                    'check_out': booking.check_out.strftime('%Y-%m-%d'),
                }
        
        # Features list
        features = []
        if room.has_ac: features.append('AC')
        if room.has_tv: features.append('TV')
        if room.has_wifi: features.append('WiFi')
        if room.has_minibar: features.append('Minibar')
        if room.has_bathroom: features.append('Bathroom')
        if room.has_balcony: features.append('Balcony')
        if room.has_kitchenette: features.append('Kitchenette')
        if room.has_safe: features.append('Safe')
        if room.has_iron: features.append('Iron')
        if room.has_hairdryer: features.append('Hairdryer')
        if room.has_phone: features.append('Phone')
        if room.has_smoking: features.append('Smoking Allowed')
        
        data = {
            'success': True,
            'room': {
                'id': room.id,
                'room_number': room.room_number,
                'room_type': room.room_type,
                'room_type_display': room.get_room_type_display(),
                'floor': room.floor,
                'capacity': room.capacity,
                'price': float(room.price),
                'status': room.status,
                'status_display': room.get_status_display(),
                'features': features,
                'description': room.description,
                'has_ac': room.has_ac,
                'has_tv': room.has_tv,
                'has_wifi': room.has_wifi,
                'has_minibar': room.has_minibar,
                'has_bathroom': room.has_bathroom,
                'has_balcony': room.has_balcony,
                'has_kitchenette': room.has_kitchenette,
                'has_safe': room.has_safe,
                'current_booking': current_booking,
            }
        }
        return JsonResponse(data)
        
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_delete_room(request, room_id):
    """API endpoint to delete a room"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        room = Room.objects.get(id=room_id, tenant=tenant)
        
        # Check if room has any active bookings
        if Booking.objects.filter(room=room, status__in=['confirmed', 'checked_in']).exists():
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete room with active bookings'
            }, status=400)
        
        room.delete()
        return JsonResponse({'success': True})
        
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_edit_room(request, room_id):
    """API endpoint to edit a room"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        room = Room.objects.get(id=room_id, tenant=tenant)
        
        # Update fields
        room.room_number = request.POST.get('room_number', room.room_number)
        room.room_type = request.POST.get('room_type', room.room_type)
        room.floor = request.POST.get('floor', room.floor)
        room.capacity = request.POST.get('capacity', room.capacity)
        room.price = request.POST.get('price', room.price)
        room.status = request.POST.get('status', room.status)
        room.description = request.POST.get('description', room.description)
        
        # Features
        room.has_ac = request.POST.get('has_ac') == 'on'
        room.has_tv = request.POST.get('has_tv') == 'on'
        room.has_wifi = request.POST.get('has_wifi') == 'on'
        room.has_minibar = request.POST.get('has_minibar') == 'on'
        room.has_bathroom = request.POST.get('has_bathroom') == 'on'
        room.has_balcony = request.POST.get('has_balcony') == 'on'
        room.has_kitchenette = request.POST.get('has_kitchenette') == 'on'
        room.has_safe = request.POST.get('has_safe') == 'on'
        room.has_iron = request.POST.get('has_iron') == 'on'
        room.has_hairdryer = request.POST.get('has_hairdryer') == 'on'
        room.has_phone = request.POST.get('has_phone') == 'on'
        room.has_smoking = request.POST.get('has_smoking') == 'on'
        
        room.save()
        
        return JsonResponse({'success': True})
        
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def api_edit_booking(request, booking_id):
    """API endpoint to edit a booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        booking = Booking.objects.get(id=booking_id, tenant=tenant)
        
        # Update fields
        booking.guest_name = request.POST.get('guest_name', booking.guest_name)
        booking.guest_phone = request.POST.get('guest_phone', booking.guest_phone)
        booking.guest_email = request.POST.get('guest_email', booking.guest_email)
        booking.guest_id_number = request.POST.get('guest_id', booking.guest_id_number)
        booking.check_in = request.POST.get('check_in', booking.check_in)
        booking.check_out = request.POST.get('check_out', booking.check_out)
        booking.status = request.POST.get('status', booking.status)
        booking.total_amount = request.POST.get('total_amount', booking.total_amount)
        booking.special_requests = request.POST.get('special_requests', booking.special_requests)
        
        booking.save()
        
        # If status changed to cancelled, make room available again
        if booking.status == 'cancelled':
            room = booking.room
            room.status = 'available'
            room.save()
        
        return JsonResponse({'success': True})
        
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Booking not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_cancel_booking(request, booking_id):
    """API endpoint to cancel a booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        booking = Booking.objects.get(id=booking_id, tenant=tenant)
        
        # Check if booking can be cancelled
        if booking.status in ['checked_out', 'cancelled']:
            return JsonResponse({
                'success': False,
                'error': f'Booking already {booking.status}'
            }, status=400)
        
        # Update booking status
        booking.status = 'cancelled'
        booking.save()
        
        # Make room available again
        room = booking.room
        room.status = 'available'
        room.save()
        
        return JsonResponse({'success': True})
        
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Booking not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
@csrf_exempt
def api_guest_checkin(request, booking_id):
    """API endpoint to check in a guest"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        data = json.loads(request.body)
        booking = Booking.objects.get(id=booking_id, tenant=tenant)
        
        # Check if booking can be checked in
        if booking.status != 'confirmed':
            return JsonResponse({
                'success': False,
                'error': f'Booking is {booking.status}, cannot check in'
            }, status=400)
        
        # Update booking
        booking.status = 'checked_in'
        booking.payment_status = data.get('payment_status', 'paid')
        booking.notes = data.get('notes', booking.notes)
        booking.save()
        
        # Update room status
        room = booking.room
        room.status = 'occupied'
        room.save()
        
        return JsonResponse({'success': True})
        
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Booking not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_guest_checkout(request, booking_id):
    """API endpoint to check out a guest"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        data = json.loads(request.body)
        booking = Booking.objects.get(id=booking_id, tenant=tenant)
        
        # Check if booking can be checked out
        if booking.status != 'checked_in':
            return JsonResponse({
                'success': False,
                'error': f'Booking is {booking.status}, cannot check out'
            }, status=400)
        
        # Update booking
        booking.status = 'checked_out'
        booking.total_amount = data.get('final_amount', booking.total_amount)
        booking.notes = data.get('notes', booking.notes)
        booking.save()
        
        # Update room status
        room = booking.room
        room.status = 'available'
        room.save()
        
        return JsonResponse({'success': True})
        
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Booking not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def api_delete_booking(request, booking_id):
    """API endpoint to delete a booking"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'success': False, 'error': 'No tenant assigned'}, status=400)
    
    try:
        booking = Booking.objects.get(id=booking_id, tenant=tenant)
        
        # Check if booking can be deleted
        if booking.status in ['checked_in']:
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete a checked-in booking'
            }, status=400)
        
        # Make room available if reserved
        if booking.status == 'confirmed':
            room = booking.room
            room.status = 'available'
            room.save()
        
        booking.delete()
        return JsonResponse({'success': True})
        
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Booking not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    

# ============================================
# REPORT VIEWS - Add these to your views.py
# ============================================

@login_required
def occupancy_report(request):
    """Hotel Occupancy Report"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get date range from request
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=30)
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
    else:
        end_date = today
    
    # Get all rooms
    total_rooms = Room.objects.filter(tenant=tenant).count()
    
    # Get occupancy data for the date range
    # We'll create a list of dates and calculate occupancy for each
    date_range = []
    current_date = start_date
    while current_date <= end_date:
        date_range.append(current_date)
        current_date += timedelta(days=1)
    
    # Calculate occupancy for each date
    occupancy_data = []
    occupied_count = 0
    available_count = 0
    
    for date in date_range:
        # Count bookings that cover this date
        occupied = Booking.objects.filter(
            tenant=tenant,
            check_in__lte=date,
            check_out__gt=date,
            status__in=['confirmed', 'checked_in']
        ).values('room').distinct().count()
        
        occupancy_rate = 0
        if total_rooms > 0:
            occupancy_rate = int((occupied / total_rooms) * 100)
        
        occupancy_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'date_label': date.strftime('%b %d'),
            'occupied': occupied,
            'total': total_rooms,
            'rate': occupancy_rate
        })
        
        occupied_count += occupied
        available_count += (total_rooms - occupied)
    
    # Calculate averages
    avg_occupied = 0
    avg_available = 0
    avg_rate = 0
    days_count = len(occupancy_data)
    
    if days_count > 0:
        avg_occupied = round(occupied_count / days_count, 1)
        avg_available = round(available_count / days_count, 1)
        if total_rooms > 0:
            avg_rate = int((avg_occupied / total_rooms) * 100)
    
    # Get room type breakdown
    room_type_stats = Room.objects.filter(tenant=tenant).values('room_type').annotate(
        total=Count('id'),
        occupied=Count('id', filter=Q(status='occupied')),
        available=Count('id', filter=Q(status='available')),
        reserved=Count('id', filter=Q(status='reserved')),
        maintenance=Count('id', filter=Q(status='maintenance'))
    )
    
    # Map room types to display names
    room_type_display = {
        'single': 'Single Room',
        'double': 'Double Room',
        'twin': 'Twin Room',
        'suite': 'Suite',
        'deluxe': 'Deluxe Suite',
        'presidential': 'Presidential Suite',
        'studio': 'Studio',
        'apartment': 'Apartment',
    }
    
    for stat in room_type_stats:
        stat['room_type_display'] = room_type_display.get(stat['room_type'], stat['room_type'].title())
        if stat['total'] > 0:
            stat['occupancy_rate'] = int((stat['occupied'] / stat['total']) * 100)
        else:
            stat['occupancy_rate'] = 0
    
    # Get daily trend data for chart
    daily_trend = []
    for date in date_range:
        occupied = Booking.objects.filter(
            tenant=tenant,
            check_in__lte=date,
            check_out__gt=date,
            status__in=['confirmed', 'checked_in']
        ).values('room').distinct().count()
        
        daily_trend.append({
            'date': date.strftime('%Y-%m-%d'),
            'occupied': occupied
        })
    
    context = {
        'tenant': tenant,
        'active_tab': 'reports',
        'report_type': 'occupancy',
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'total_rooms': total_rooms,
        'avg_occupied': avg_occupied,
        'avg_available': avg_available,
        'avg_rate': avg_rate,
        'room_type_stats': room_type_stats,
        'occupancy_data': occupancy_data,
        'daily_trend': daily_trend,
        'date_range': date_range,
    }
    
    template_path = get_template_path('occupancy_report.html', tenant)
    return render(request, template_path, context)


@login_required
def revenue_report(request):
    """Hotel Revenue Report"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get date range from request
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=30)
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
    else:
        end_date = today
    
    # Get bookings within date range
    bookings = Booking.objects.filter(
        tenant=tenant,
        check_in__lte=end_date,
        check_out__gte=start_date,
        status__in=['confirmed', 'checked_in', 'checked_out']
    )
    
    # Total revenue
    total_revenue = bookings.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Paid vs Pending
    paid_amount = bookings.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
    pending_amount = bookings.filter(payment_status='pending').aggregate(total=Sum('total_amount'))['total'] or 0
    partial_amount = bookings.filter(payment_status='partial').aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Room type revenue breakdown
    room_type_revenue = bookings.values('room__room_type').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('-total')
    
    room_type_display = {
        'single': 'Single Room',
        'double': 'Double Room',
        'twin': 'Twin Room',
        'suite': 'Suite',
        'deluxe': 'Deluxe Suite',
        'presidential': 'Presidential Suite',
        'studio': 'Studio',
        'apartment': 'Apartment',
    }
    
    for item in room_type_revenue:
        item['room_type_display'] = room_type_display.get(item['room__room_type'], item['room__room_type'].title())
    
    # Monthly revenue breakdown
    monthly_revenue = []
    current_date = start_date
    while current_date <= end_date:
        month_start = current_date.replace(day=1)
        if current_date.month == 12:
            month_end = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
        
        month_booking = Booking.objects.filter(
            tenant=tenant,
            check_in__lte=month_end,
            check_out__gte=month_start,
            status__in=['confirmed', 'checked_in', 'checked_out']
        )
        
        month_total = month_booking.aggregate(total=Sum('total_amount'))['total'] or 0
        month_count = month_booking.count()
        
        monthly_revenue.append({
            'month': current_date.strftime('%b %Y'),
            'year': current_date.year,
            'month_num': current_date.month,
            'total': month_total,
            'count': month_count
        })
        
        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1, day=1)
    
    # Daily revenue trend
    daily_revenue = []
    current_date = start_date
    while current_date <= end_date:
        daily_booking = Booking.objects.filter(
            tenant=tenant,
            check_in__lte=current_date,
            check_out__gte=current_date,
            status__in=['confirmed', 'checked_in', 'checked_out']
        )
        daily_total = daily_booking.aggregate(total=Sum('total_amount'))['total'] or 0
        
        daily_revenue.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'date_label': current_date.strftime('%b %d'),
            'total': daily_total,
        })
        
        current_date += timedelta(days=1)
    
    # Revenue by day of week
    day_of_week_revenue = {
        'Monday': 0.0,
        'Tuesday': 0.0,
        'Wednesday': 0.0,
        'Thursday': 0.0,
        'Friday': 0.0,
        'Saturday': 0.0,
        'Sunday': 0.0,
    }
    
    for booking in bookings:
        if booking.check_in:
            day_name = booking.check_in.strftime('%A')
            day_of_week_revenue[day_name] = day_of_week_revenue.get(day_name, 0.0) + float(booking.total_amount or 0)
    
    # Calculate averages and statistics
    total_days = (end_date - start_date).days + 1
    avg_daily_revenue = 0
    if total_days > 0:
        avg_daily_revenue = total_revenue / total_days
    
    context = {
        'tenant': tenant,
        'active_tab': 'reports',
        'report_type': 'revenue',
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'total_revenue': total_revenue,
        'paid_amount': paid_amount,
        'pending_amount': pending_amount,
        'partial_amount': partial_amount,
        'avg_daily_revenue': avg_daily_revenue,
        'total_bookings': bookings.count(),
        'room_type_revenue': room_type_revenue,
        'monthly_revenue': monthly_revenue,
        'daily_revenue': daily_revenue,
        'day_of_week_revenue': day_of_week_revenue,
    }
    
    template_path = get_template_path('revenue_report.html', tenant)
    return render(request, template_path, context)


@login_required
def expense_list(request):
    """Hotel Expense List"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get date range
    today = timezone.now().date()
    start_date_str = request.GET.get('start_date', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date_str = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=30)
        start_date_str = start_date.strftime('%Y-%m-%d')
    
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        end_date = today
        end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Query the shared Expense model
    from apps.shared.expenses.models import Expense
    from django.db.models import Sum
    
    expenses_query = Expense.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('category', 'created_by').order_by('-date')
    
    total_expenses = expenses_query.aggregate(total=Sum('amount'))['total'] or 0
    
    # Format expenses for display
    expenses = []
    for exp in expenses_query:
        expenses.append({
            'id': exp.id,
            'category': exp.category.name if exp.category else 'Uncategorized',
            'description': exp.description or exp.category.name if exp.category else 'Expense',
            'amount': float(exp.amount),
            'date': exp.date.strftime('%Y-%m-%d'),
            'paid_by': exp.created_by.get_full_name() if exp.created_by else 'System',
        })
    
    # REMOVED: The mock data section - No fake data will be shown
    
    context = {
        'tenant': tenant,
        'active_tab': 'reports',
        'start_date': start_date_str,
        'end_date': end_date_str,
        'expenses': expenses,  # Will be empty if no expenses exist
        'total_expenses': total_expenses,
    }
    
    template_path = get_template_path('expense_list.html', tenant)
    return render(request, template_path, context)


@login_required
def report_dashboard(request):
    """Report Dashboard - Combined view"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    today = timezone.now().date()
    
    # Quick stats
    total_bookings = Booking.objects.filter(tenant=tenant).count()
    active_bookings = Booking.objects.filter(
        tenant=tenant,
        status__in=['confirmed', 'checked_in']
    ).count()
    
    total_revenue = Booking.objects.filter(tenant=tenant).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Monthly stats
    month_start = today.replace(day=1)
    month_bookings = Booking.objects.filter(
        tenant=tenant,
        check_in__gte=month_start,
        status__in=['confirmed', 'checked_in', 'checked_out']
    )
    month_revenue = month_bookings.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Occupancy rate
    total_rooms = Room.objects.filter(tenant=tenant).count()
    occupied_rooms = Room.objects.filter(tenant=tenant, status='occupied').count()
    occupancy_rate = 0
    if total_rooms > 0:
        occupancy_rate = int((occupied_rooms / total_rooms) * 100)
    
    context = {
        'tenant': tenant,
        'active_tab': 'reports',
        'total_bookings': total_bookings,
        'active_bookings': active_bookings,
        'total_revenue': total_revenue,
        'month_revenue': month_revenue,
        'occupancy_rate': occupancy_rate,
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'month_name': month_start.strftime('%B'),
    }
    
    template_path = get_template_path('report_dashboard.html', tenant)
    return render(request, template_path, context)


# ===================================
# HOTEL MASTER SETTINGS VIEWS
# ===================================

from apps.shared.settings.models import HotelSetting

@login_required
def hotel_settings(request):
    """Hotel Master Hotel Settings"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get or create hotel settings
    settings, created = HotelSetting.objects.get_or_create(tenant=tenant)
    
    if request.method == 'POST':
        # Hotel Details
        settings.hotel_name = request.POST.get('hotel_name', '')
        settings.hotel_address = request.POST.get('hotel_address', '')
        settings.hotel_phone = request.POST.get('hotel_phone', '')
        settings.hotel_email = request.POST.get('hotel_email', '')
        settings.hotel_website = request.POST.get('hotel_website', '')
        settings.hotel_description = request.POST.get('hotel_description', '')
        
        # Check-in / Check-out Times
        settings.check_in_time = request.POST.get('check_in_time', '14:00')
        settings.check_out_time = request.POST.get('check_out_time', '11:00')
        
        # Policies
        settings.cancellation_policy = request.POST.get('cancellation_policy', '')
        settings.early_checkin_policy = request.POST.get('early_checkin_policy', '')
        settings.late_checkout_policy = request.POST.get('late_checkout_policy', '')
        settings.payment_policy = request.POST.get('payment_policy', '')
        
        # Financial Settings
        settings.currency = request.POST.get('currency', 'KES')
        settings.tax_rate = request.POST.get('tax_rate', 0)
        settings.service_charge = request.POST.get('service_charge', 0)
        
        settings.save()
        messages.success(request, 'Hotel settings updated successfully!')
        return redirect('hotel_master:hotel_settings')
    
    context = {
        'tenant': tenant,
        'settings': settings,
        'active_tab': 'settings',
    }
    return render(request, 'hotel_master/hotel_settings.html', context)


@login_required
def receipt_settings(request):
    """Hotel Master Receipt Settings"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('hotel_master:dashboard')
    
    from apps.shared.settings.models import ReceiptSetting
    
    # Get or create receipt settings
    settings, created = ReceiptSetting.objects.get_or_create(tenant=tenant)
    
    if request.method == 'POST':
        # Business Details
        settings.business_name = request.POST.get('business_name', '')
        settings.business_address = request.POST.get('business_address', '')
        settings.business_phone = request.POST.get('business_phone', '')
        settings.business_email = request.POST.get('business_email', '')
        settings.business_tax_pin = request.POST.get('business_tax_pin', '')
        
        # Toggles
        settings.show_business_name = request.POST.get('show_business_name') == 'on'
        settings.show_address = request.POST.get('show_address') == 'on'
        settings.show_phone = request.POST.get('show_phone') == 'on'
        settings.show_email = request.POST.get('show_email') == 'on'
        settings.show_tax_pin = request.POST.get('show_tax_pin') == 'on'
        settings.show_receipt_number = request.POST.get('show_receipt_number') == 'on'
        settings.show_sale_date = request.POST.get('show_sale_date') == 'on'
        settings.show_sale_time = request.POST.get('show_sale_time') == 'on'
        settings.show_footer_message = request.POST.get('show_footer_message') == 'on'
        settings.footer_text = request.POST.get('footer_text', 'Thank you for staying with us!')
        
        settings.save()
        messages.success(request, 'Receipt settings updated successfully!')
        return redirect('settings:receipt_settings')
    
    context = {
        'tenant': tenant,
        'settings': settings,
        'active_tab': 'settings',
    }
    return render(request, 'shared/settings/receipt_settings.html', context)


@login_required
def profile_settings(request):
    """Hotel Master Profile Settings"""
    user = request.user
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('hotel_master:dashboard')
    
    from apps.shared.settings.models import ProfileSetting
    from apps.shared.users.models import User as AuthUser
    
    # Get or create profile settings
    settings, created = ProfileSetting.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        # Personal Info
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        
        # Username
        new_username = request.POST.get('username', '').strip()
        if new_username and new_username != user.username:
            if AuthUser.objects.filter(username=new_username).exists():
                messages.error(request, f'Username "{new_username}" is already taken.')
            else:
                user.username = new_username
                messages.success(request, 'Username updated!')
        
        # Change Password
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if current_password and new_password:
            if not check_password(current_password, user.password):
                messages.error(request, 'Current password is incorrect.')
            elif new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
            elif len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
            else:
                user.set_password(new_password)
                messages.success(request, 'Password changed successfully!')
        
        # PIN
        current_pin = request.POST.get('current_pin')
        new_pin = request.POST.get('new_pin')
        
        if current_pin and new_pin:
            if user.pin_code and current_pin != user.pin_code:
                messages.error(request, 'Current PIN is incorrect.')
            elif not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 6:
                messages.error(request, 'PIN must be 4-6 digits.')
            else:
                user.pin_code = new_pin
                messages.success(request, 'PIN updated!')
        
        # Profile Settings
        settings.theme = request.POST.get('theme', settings.theme)
        settings.language = request.POST.get('language', settings.language)
        settings.currency = request.POST.get('currency', settings.currency)
        settings.notifications_enabled = request.POST.get('notifications_enabled') == 'on'
        settings.email_notifications = request.POST.get('email_notifications') == 'on'
        
        # Save
        user.save()
        settings.save()
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Profile settings updated successfully!')
        return redirect('hotel_master:profile_settings')
    
    # Available options
    themes = [
        {'value': 'light', 'label': 'Light'},
        {'value': 'dark', 'label': 'Dark'},
        {'value': 'auto', 'label': 'Auto'},
    ]
    
    languages = [
        {'value': 'en', 'label': 'English'},
        {'value': 'sw', 'label': 'Swahili'},
    ]
    
    currencies = [
        {'value': 'KES', 'label': 'Kenyan Shilling (KES)'},
        {'value': 'USD', 'label': 'US Dollar (USD)'},
        {'value': 'EUR', 'label': 'Euro (EUR)'},
    ]
    
    context = {
        'tenant': tenant,
        'user': user,
        'settings': settings,
        'themes': themes,
        'languages': languages,
        'currencies': currencies,
        'active_tab': 'settings',
    }
    return render(request, 'hotel_master/profile_settings.html', context)