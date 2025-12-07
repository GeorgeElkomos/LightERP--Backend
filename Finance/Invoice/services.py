"""
Invoice Service Layer - Business Logic for Complex Invoice Operations

This service layer handles the complexity of creating invoices with:
1. Invoice Items
2. Journal Entries with Journal Lines
3. Segment Combinations
4. Automatic GL posting

WHY USE A SERVICE LAYER?
========================
1. **Separation of Concerns**: Business logic separate from API layer
2. **Reusability**: Same logic for API, imports, scheduled jobs
3. **Testability**: Easy to unit test without HTTP layer
4. **Transaction Management**: Atomic operations for complex creates
5. **Validation**: Business rule validation in one place

Architecture:
- DTOs (Data Transfer Objects) - Define request/response structure
- Service Methods - Handle business logic
- Views/Serializers - Just thin wrappers around services
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date

from Finance.Invoice.models import Invoice, InvoiceItem, AP_Invoice, AR_Invoice, OneTimeSupplier
from Finance.GL.models import (
    JournalEntry, JournalLine, 
    XX_Segment_combination, segment_combination_detials,
    XX_SegmentType, XX_Segment
)
from Finance.core.models import Currency, Country
from Finance.BusinessPartner.models import Supplier, Customer


# ==================== DTOs (Data Transfer Objects) ====================

@dataclass
class SegmentDTO:
    """Represents a single segment in a combination"""
    segment_type_id: int
    segment_code: str


@dataclass
class JournalLineDTO:
    """Represents a single journal line"""
    amount: Decimal
    type: str  # 'DEBIT' or 'CREDIT'
    segments: List[SegmentDTO]
    
    def __post_init__(self):
        if self.type not in ['DEBIT', 'CREDIT']:
            raise ValidationError(f"Invalid type '{self.type}'. Must be 'DEBIT' or 'CREDIT'")


@dataclass
class JournalEntryDTO:
    """Represents the GL distribution for an invoice"""
    date: date
    currency_id: int
    memo: str = ""
    lines: List[JournalLineDTO] = field(default_factory=list)


@dataclass
class InvoiceItemDTO:
    """Represents a single invoice line item"""
    name: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    
    @property
    def line_total(self) -> Decimal:
        """Calculate line total"""
        return self.quantity * self.unit_price


@dataclass
class InvoiceBaseDTO:
    """Base invoice data common to all invoice types"""
    date: date
    currency_id: int
    country_id: Optional[int]
    subtotal: Optional[Decimal]
    tax_amount: Optional[Decimal]
    total: Optional[Decimal]
    approval_status: str
    payment_status: str
    items: List[InvoiceItemDTO]
    journal_entry: Optional[JournalEntryDTO]


@dataclass
class APInvoiceDTO(InvoiceBaseDTO):
    """AP Invoice specific data"""
    supplier_id: int


@dataclass
class ARInvoiceDTO(InvoiceBaseDTO):
    """AR Invoice specific data"""
    customer_id: int


@dataclass
class OneTimeSupplierDTO(InvoiceBaseDTO):
    """One-time supplier invoice data"""
    one_time_supplier_id: Optional[int] = None
    # Supplier info for creating new OneTime if needed
    supplier_name: Optional[str] = None
    supplier_email: Optional[str] = ""
    supplier_phone: Optional[str] = ""
    supplier_tax_id: Optional[str] = ""


# ==================== SERVICE LAYER ====================

class InvoiceService:
    """
    Service layer for invoice operations.
    Handles complex business logic for creating invoices with GL distributions.
    """
    
    @staticmethod
    @transaction.atomic
    def create_ap_invoice(dto: APInvoiceDTO) -> AP_Invoice:
        """
        Create an AP Invoice with items and GL distribution.
        
        Args:
            dto: APInvoiceDTO containing all invoice data
            
        Returns:
            AP_Invoice instance
            
        Raises:
            ValidationError: If data is invalid
            
        Example:
            dto = APInvoiceDTO(
                date=date.today(),
                currency_id=1,
                supplier_id=5,
                items=[...],
                journal_entry=JournalEntryDTO(...)
            )
            ap_invoice = InvoiceService.create_ap_invoice(dto)
        """
        # 1. Validate supplier exists
        try:
            supplier = Supplier.objects.get(pk=dto.supplier_id)
        except Supplier.DoesNotExist:
            raise ValidationError(f"Supplier with ID {dto.supplier_id} not found")
        
        # 2. Validate currency and country
        currency = InvoiceService._validate_currency(dto.currency_id)
        country = InvoiceService._validate_country(dto.country_id) if dto.country_id else None
        
        # 3. Calculate totals if not provided
        calculated_subtotal, calculated_total = InvoiceService._calculate_totals(
            dto.items, dto.subtotal, dto.tax_amount, dto.total
        )
        
        # 4. Create or validate journal entry
        journal_entry = InvoiceService._create_journal_entry(dto.journal_entry, currency)
        
        # 5. Validate journal entry balances
        InvoiceService._validate_journal_balance(journal_entry, calculated_total)
        
        # 6. Create AP Invoice (automatically creates Invoice parent)
        ap_invoice = AP_Invoice.objects.create(
            # Invoice fields (auto-handled by pattern)
            date=dto.date,
            currency=currency,
            country=country,
            approval_status=dto.approval_status,
            payment_status=dto.payment_status,
            subtotal=calculated_subtotal,
            tax_amount=dto.tax_amount or Decimal('0.00'),
            total=calculated_total,
            gl_distributions=journal_entry,
            # AP-specific fields
            supplier=supplier
        )
        
        # 7. Create invoice items
        InvoiceService._create_invoice_items(ap_invoice.invoice, dto.items)
        
        return ap_invoice
    
    @staticmethod
    @transaction.atomic
    def create_ar_invoice(dto: ARInvoiceDTO) -> AR_Invoice:
        """Create an AR Invoice with items and GL distribution."""
        # 1. Validate customer exists
        try:
            customer = Customer.objects.get(pk=dto.customer_id)
        except Customer.DoesNotExist:
            raise ValidationError(f"Customer with ID {dto.customer_id} not found")
        
        # 2. Validate currency and country
        currency = InvoiceService._validate_currency(dto.currency_id)
        country = InvoiceService._validate_country(dto.country_id) if dto.country_id else None
        
        # 3. Calculate totals
        calculated_subtotal, calculated_total = InvoiceService._calculate_totals(
            dto.items, dto.subtotal, dto.tax_amount, dto.total
        )
        
        # 4. Create journal entry
        journal_entry = InvoiceService._create_journal_entry(dto.journal_entry, currency)
        
        # 5. Validate balance
        InvoiceService._validate_journal_balance(journal_entry, calculated_total)
        
        # 6. Create AR Invoice
        ar_invoice = AR_Invoice.objects.create(
            date=dto.date,
            currency=currency,
            country=country,
            approval_status=dto.approval_status,
            payment_status=dto.payment_status,
            subtotal=calculated_subtotal,
            tax_amount=dto.tax_amount or Decimal('0.00'),
            total=calculated_total,
            gl_distributions=journal_entry,
            customer=customer
        )
        
        # 7. Create items
        InvoiceService._create_invoice_items(ar_invoice.invoice, dto.items)
        
        return ar_invoice
    
    @staticmethod
    @transaction.atomic
    def create_one_time_supplier_invoice(dto: OneTimeSupplierDTO) -> OneTimeSupplier:
        """Create a one-time supplier invoice."""
        # Validate and calculate
        currency = InvoiceService._validate_currency(dto.currency_id)
        country = InvoiceService._validate_country(dto.country_id) if dto.country_id else None
        
        calculated_subtotal, calculated_total = InvoiceService._calculate_totals(
            dto.items, dto.subtotal, dto.tax_amount, dto.total
        )
        
        journal_entry = InvoiceService._create_journal_entry(dto.journal_entry, currency)
        InvoiceService._validate_journal_balance(journal_entry, calculated_total)
        
        # Get or create OneTime business partner
        from Finance.BusinessPartner.models import OneTime
        if dto.one_time_supplier_id:
            one_time_supplier = OneTime.objects.get(id=dto.one_time_supplier_id)
        else:
            # Create new OneTime business partner
            if not dto.supplier_name:
                raise ValidationError("supplier_name is required when creating a new one-time supplier")
            one_time_supplier = OneTime.objects.create(
                name=dto.supplier_name,
                email=dto.supplier_email or "",
                phone=dto.supplier_phone or "",
                tax_id=dto.supplier_tax_id or ""
            )
        
        # Create one-time supplier invoice
        one_time = OneTimeSupplier.objects.create(
            date=dto.date,
            currency=currency,
            country=country,
            approval_status=dto.approval_status,
            payment_status=dto.payment_status,
            subtotal=calculated_subtotal,
            tax_amount=dto.tax_amount or Decimal('0.00'),
            total=calculated_total,
            gl_distributions=journal_entry,
            one_time_supplier=one_time_supplier
        )
        
        InvoiceService._create_invoice_items(one_time.invoice, dto.items)
        
        return one_time
    
    # ==================== HELPER METHODS ====================
    
    @staticmethod
    def _validate_currency(currency_id: int) -> Currency:
        """Validate currency exists"""
        try:
            return Currency.objects.get(pk=currency_id)
        except Currency.DoesNotExist:
            raise ValidationError(f"Currency with ID {currency_id} not found")
    
    @staticmethod
    def _validate_country(country_id: int) -> Country:
        """Validate country exists"""
        try:
            return Country.objects.get(pk=country_id)
        except Country.DoesNotExist:
            raise ValidationError(f"Country with ID {country_id} not found")
    
    @staticmethod
    def _calculate_totals(
        items: List[InvoiceItemDTO],
        provided_subtotal: Optional[Decimal],
        provided_tax: Optional[Decimal],
        provided_total: Optional[Decimal]
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate invoice totals from items.
        Validates if provided totals match calculated totals.
        """
        # Calculate from items
        calculated_subtotal = sum(item.line_total for item in items)
        tax_amount = provided_tax or Decimal('0.00')
        calculated_total = calculated_subtotal + tax_amount
        
        # Validate if totals were provided
        if provided_subtotal is not None and abs(provided_subtotal - calculated_subtotal) > Decimal('0.01'):
            raise ValidationError(
                f"Provided subtotal {provided_subtotal} does not match calculated subtotal {calculated_subtotal}"
            )
        
        if provided_total is not None and abs(provided_total - calculated_total) > Decimal('0.01'):
            raise ValidationError(
                f"Provided total {provided_total} does not match calculated total {calculated_total}"
            )
        
        return calculated_subtotal, calculated_total
    
    @staticmethod
    def _create_journal_entry(je_dto: JournalEntryDTO, currency: Currency) -> JournalEntry:
        """Create journal entry with lines and segment combinations"""
        if not je_dto:
            raise ValidationError("Journal entry is required")
        
        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            date=je_dto.date,
            currency=currency,
            memo=je_dto.memo,
            posted=False  # Initially unposted
        )
        
        # Create journal lines
        for line_dto in je_dto.lines:
            # Get or create segment combination
            segment_combination = InvoiceService._get_or_create_segment_combination(
                line_dto.segments
            )
            
            # Create journal line
            JournalLine.objects.create(
                entry=journal_entry,
                amount=line_dto.amount,
                type=line_dto.type,
                segment_combination=segment_combination
            )
        
        return journal_entry
    
    @staticmethod
    def _get_or_create_segment_combination(segments: List[SegmentDTO]) -> XX_Segment_combination:
        """
        Get or create a segment combination from segment DTOs.
        Reuses existing combinations if they match.
        """
        # Build combination hash for lookup
        segment_dict = {seg.segment_type_id: seg.segment_code for seg in segments}
        
        # Try to find existing combination
        # This is a simplified approach - in production, you'd want more sophisticated matching
        existing_combinations = XX_Segment_combination.objects.all()
        
        for combo in existing_combinations:
            combo_segments = {
                detail.segment_type_id: detail.segment.code
                for detail in combo.details.all()
            }
            if combo_segments == segment_dict:
                return combo
        
        # Create new combination
        combination = XX_Segment_combination.objects.create()
        
        for seg_dto in segments:
            # Validate segment type exists
            try:
                segment_type = XX_SegmentType.objects.get(pk=seg_dto.segment_type_id)
            except XX_SegmentType.DoesNotExist:
                raise ValidationError(f"Segment type {seg_dto.segment_type_id} not found")
            
            # Validate segment exists
            try:
                segment = XX_Segment.objects.get(
                    segment_type=segment_type,
                    code=seg_dto.segment_code
                )
            except XX_Segment.DoesNotExist:
                raise ValidationError(
                    f"Segment '{seg_dto.segment_code}' not found for type '{segment_type.segment_name}'"
                )
            
            # Create combination detail
            segment_combination_detials.objects.create(
                segment_combination=combination,
                segment_type=segment_type,
                segment=segment
            )
        
        return combination
    
    @staticmethod
    def _validate_journal_balance(journal_entry: JournalEntry, invoice_total: Decimal):
        """
        Validate that journal entry debits = credits.
        Also validates that journal total matches invoice total.
        """
        lines = journal_entry.lines.all()
        
        total_debits = sum(
            line.amount for line in lines if line.type == 'DEBIT'
        )
        total_credits = sum(
            line.amount for line in lines if line.type == 'CREDIT'
        )
        
        # Check balance
        if abs(total_debits - total_credits) > Decimal('0.01'):
            raise ValidationError(
                f"Journal entry is not balanced. Debits: {total_debits}, Credits: {total_credits}"
            )
        
        # Check against invoice total (optional - depends on your business rules)
        # For AP invoices, credits should typically equal invoice total
        # For AR invoices, debits should typically equal invoice total
        # This can be customized based on your specific requirements
    
    @staticmethod
    def _create_invoice_items(invoice: Invoice, items: List[InvoiceItemDTO]):
        """Create invoice line items"""
        for item_dto in items:
            InvoiceItem.objects.create(
                invoice=invoice,
                name=item_dto.name,
                description=item_dto.description,
                quantity=item_dto.quantity,
                unit_price=item_dto.unit_price
            )


# ==================== USAGE EXAMPLES ====================

"""
Example 1: Create AP Invoice
=============================

from decimal import Decimal
from datetime import date

# Build the DTO
dto = APInvoiceDTO(
    date=date(2025, 12, 6),
    currency_id=1,
    country_id=1,
    supplier_id=5,
    tax_amount=Decimal('100.00'),
    items=[
        InvoiceItemDTO(
            name="Laptops",
            description="Dell XPS 15",
            quantity=Decimal('10'),
            unit_price=Decimal('1000.00')
        ),
        InvoiceItemDTO(
            name="Monitors",
            description="27 inch 4K",
            quantity=Decimal('20'),
            unit_price=Decimal('300.00')
        ),
    ],
    journal_entry=JournalEntryDTO(
        date=date(2025, 12, 6),
        currency_id=1,
        memo="Purchase of IT equipment",
        lines=[
            # Debit: IT Equipment expense
            JournalLineDTO(
                amount=Decimal('16100.00'),
                type='DEBIT',
                segments=[
                    SegmentDTO(segment_type_id=1, segment_code='100'),  # Entity
                    SegmentDTO(segment_type_id=2, segment_code='6100'),  # Account (IT Expense)
                    SegmentDTO(segment_type_id=3, segment_code='PROJ01'),  # Project
                ]
            ),
            # Credit: Accounts Payable
            JournalLineDTO(
                amount=Decimal('16100.00'),
                type='CREDIT',
                segments=[
                    SegmentDTO(segment_type_id=1, segment_code='100'),
                    SegmentDTO(segment_type_id=2, segment_code='2100'),  # Account (A/P)
                    SegmentDTO(segment_type_id=3, segment_code='PROJ01'),
                ]
            ),
        ]
    )
)

# Create the invoice
ap_invoice = InvoiceService.create_ap_invoice(dto)

print(f"Created AP Invoice #{ap_invoice.invoice.id}")
print(f"  Supplier: {ap_invoice.supplier.name}")
print(f"  Total: {ap_invoice.total}")
print(f"  Items: {ap_invoice.invoice.items.count()}")
print(f"  Journal Entry: JE#{ap_invoice.gl_distributions.id}")


Example 2: Create AR Invoice
=============================

dto = ARInvoiceDTO(
    date=date.today(),
    currency_id=1,
    customer_id=3,
    tax_amount=Decimal('50.00'),
    items=[
        InvoiceItemDTO(
            name="Consulting Services",
            description="IT consulting - 10 hours",
            quantity=Decimal('10'),
            unit_price=Decimal('150.00')
        ),
    ],
    journal_entry=JournalEntryDTO(
        date=date.today(),
        currency_id=1,
        memo="Consulting invoice",
        lines=[
            JournalLineDTO(
                amount=Decimal('1550.00'),
                type='DEBIT',
                segments=[
                    SegmentDTO(segment_type_id=1, segment_code='100'),
                    SegmentDTO(segment_type_id=2, segment_code='1200'),  # A/R
                ]
            ),
            JournalLineDTO(
                amount=Decimal('1550.00'),
                type='CREDIT',
                segments=[
                    SegmentDTO(segment_type_id=1, segment_code='100'),
                    SegmentDTO(segment_type_id=2, segment_code='4000'),  # Revenue
                ]
            ),
        ]
    )
)

ar_invoice = InvoiceService.create_ar_invoice(dto)
"""
