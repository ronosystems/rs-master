# apps/hotel_master/models.py

from django.db import models
from apps.shared.tenants.models import Tenant
from apps.shared.users.models import User
from django.utils import timezone
import random
import datetime
from decimal import Decimal


class Room(models.Model):
    """Hotel Room Model"""
    
    ROOM_TYPES = [
        ('standard', 'Standard'),
        ('deluxe', 'Deluxe'),
        ('suite', 'Suite'),
        ('executive', 'Executive'),
        ('presidential', 'Presidential'),
        ('family', 'Family'),
        ('single', 'Single'),
        ('double', 'Double'),
        ('twin', 'Twin'),
        ('studio', 'Studio'),
        ('penthouse', 'Penthouse'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Maintenance'),
        ('cleaning', 'Cleaning'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hotel_rooms')
    room_number = models.CharField(max_length=20)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='standard')
    floor = models.PositiveIntegerField(default=1)
    capacity = models.PositiveIntegerField(default=2)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    
    # Features
    has_ac = models.BooleanField(default=True)
    has_tv = models.BooleanField(default=True)
    has_wifi = models.BooleanField(default=True)
    has_minibar = models.BooleanField(default=False)
    has_bathroom = models.BooleanField(default=True)
    has_balcony = models.BooleanField(default=False)
    has_kitchenette = models.BooleanField(default=False)
    has_safe = models.BooleanField(default=False)
    has_iron = models.BooleanField(default=False)
    has_hairdryer = models.BooleanField(default=False)
    has_phone = models.BooleanField(default=False)
    has_smoking = models.BooleanField(default=False)
    
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['room_number']
        unique_together = [['tenant', 'room_number']]
    
    def __str__(self):
        return f"{self.room_number} - {self.get_room_type_display()}"
    
    def save(self, *args, **kwargs):
        if not self.room_number:
            # Generate room number if not provided
            last_room = Room.objects.filter(tenant=self.tenant).order_by('-id').first()
            if last_room:
                try:
                    num = int(last_room.room_number) + 1
                    self.room_number = str(num).zfill(3)
                except:
                    self.room_number = '001'
            else:
                self.room_number = '001'
        super().save(*args, **kwargs)


class Booking(models.Model):
    """Hotel Booking Model"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partial Payment'),
        ('deposit', 'Deposit Paid'),
        ('refunded', 'Refunded'),
    ]
    
    BOOKING_TYPES = [
        ('standard', 'Standard'),
        ('vip', 'VIP'),
        ('corporate', 'Corporate'),
        ('group', 'Group'),
        ('walk_in', 'Walk-in'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hotel_bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    
    booking_number = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Guest Details
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField(blank=True, null=True)
    guest_phone = models.CharField(max_length=20)
    guest_id_number = models.CharField(max_length=50, blank=True, null=True)
    guest_address = models.TextField(blank=True, null=True)
    
    # Booking Details
    check_in = models.DateField()
    check_out = models.DateField()
    number_of_guests = models.PositiveIntegerField(default=1)
    booking_type = models.CharField(max_length=20, choices=BOOKING_TYPES, default='standard')
    special_requests = models.TextField(blank=True, null=True)
    
    # Payment
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=20, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_bookings'
    )
    checked_in_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checked_in_bookings'
    )
    checked_out_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checked_out_bookings'
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'booking_number']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['check_in', 'check_out']),
            models.Index(fields=['guest_phone']),
        ]
    
    def __str__(self):
        return f"{self.booking_number} - {self.guest_name}"
    
    def save(self, *args, **kwargs):
        if not self.booking_number:
            self.booking_number = self._generate_booking_number()
        super().save(*args, **kwargs)
    
    def _generate_booking_number(self):
        date_str = datetime.datetime.now().strftime('%Y%m%d')
        random_num = random.randint(10000, 99999)
        return f"BK-{date_str}-{random_num}"
    
    def perform_check_in(self, user):
        """Check in the guest"""
        self.status = 'checked_in'
        self.checked_in_by = user
        self.checked_in_at = timezone.now()
        self.save()
        
        # Update room status
        room = self.room
        room.status = 'occupied'
        room.save()
    
    def perform_check_out(self, user):
        """Check out the guest"""
        self.status = 'checked_out'
        self.checked_out_by = user
        self.checked_out_at = timezone.now()
        self.save()
        
        # Update room status
        room = self.room
        room.status = 'available'
        room.save()
    
    @property
    def nights(self):
        """Calculate number of nights"""
        if self.check_in and self.check_out:
            return (self.check_out - self.check_in).days
        return 0
    
    @property
    def is_checked_in(self):
        return self.status == 'checked_in'
    
    @property
    def is_checked_out(self):
        return self.status == 'checked_out'
    
    @property
    def is_confirmed(self):
        return self.status == 'confirmed'
