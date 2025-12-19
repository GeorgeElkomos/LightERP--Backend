from django.db import models
from django.conf import settings
from decimal import Decimal
from datetime import date
from Finance.core.models import Currency
from Finance.BusinessPartner.models import BusinessPartner
from procurement.PR.models import PR
"""Purchase Order Header."""
class POHeader(models.Model):    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('CONFIRMED', 'Confirmed/Sent to Vendor'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('CANCELLED', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    
    
    # PO Type (same as PR Type)
    PO_TYPE_CHOICES = [
        ('CATEGORIZED_GOODS', 'Categorized Goods'),
        ('UNCATEGORIZED_GOODS', 'Uncategorized Goods'),
        ('SERVICES', 'Services'),
    ]
    
    # PO Information
    po_number = models.CharField(max_length=50, unique=True, db_index=True)
    po_date = models.DateField(default=date.today)
    po_type = models.CharField(
        max_length=30,
        choices=PO_TYPE_CHOICES,
        default='UNCATEGORIZED_GOODS',
        help_text="Type of PO: Categorized Goods, Uncategorized Goods, or Services"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    
    # Source PR Headers - Track multiple PRs that contribute to this PO
    source_pr_headers = models.ManyToManyField(
        PR,
        blank=True,
        related_name='converted_pos',
        help_text="Source PR Headers that contribute to this PO"
    )
    
    # Vendor Information - using string for now until Vendor model is ready
    suplier_name = models.ForeignKey(BusinessPartner, on_delete=models.PROTECT, help_text="Vendor/Supplier")
    # Delivery Information
    reciving_date = models.DateField(null=True, blank=True)
    reciving_address = models.TextField(blank=True)
    reciver_email = models.EmailField(max_length=200, blank=True)
    reciver_contact = models.CharField(max_length=200, blank=True)
    reciver_phone = models.CharField(max_length=50, blank=True)
    
    
    # Financial - Transaction Currency
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, help_text="Transaction currency")
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Subtotal in transaction currency")
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Tax in transaction currency")
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Discount in transaction currency")
    shipping_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Shipping in transaction currency")
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Total in transaction currency")
    
    # Multi-Currency Support
    exchange_rate = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        default=Decimal('1.000000'),
        help_text="Exchange rate from transaction currency to base currency"
    )
    base_currency_subtotal = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Subtotal in base currency"
    )
    base_currency_total = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total amount in base currency"
    )
    
   # Notes
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Workflow
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='purchase_orders_created')
    created_at = models.DateTimeField(auto_now_add=True)
    
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_submitted')
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_confirmed')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_cancelled')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
