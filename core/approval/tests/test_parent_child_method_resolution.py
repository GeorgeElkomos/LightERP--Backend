"""
Test to demonstrate method resolution in parent-child approval pattern.

This test answers the critical question:
"When approval workflow calls methods on the parent Invoice,
can the child AP_Invoice override those methods?"

ANSWER: NO - Because of the OneToOne relationship structure!

The workflow is attached to Invoice (parent) instance.
When workflow calls invoice.on_stage_approved(), it calls
the method on the Invoice instance, NOT the child.

SOLUTION: See below for the correct pattern to use.
"""

from django.test import TestCase


class MethodResolutionExplanation(TestCase):
    """
    Demonstrates the method resolution challenge with OneToOne relationships.
    """
    
    def test_explain_the_problem(self):
        """
        THE PROBLEM:
        ============
        
        With your current structure:
        
        class Invoice(models.Model):
            def on_stage_approved(self, stage):
                print("Parent method called")
        
        class AP_Invoice(models.Model):
            invoice = models.OneToOneField(Invoice, primary_key=True)
            
            def on_stage_approved(self, stage):
                print("Child method called - THIS WON'T BE CALLED!")
        
        # When workflow runs:
        workflow = ApprovalManager.start_workflow(ap_invoice.invoice)  # ← parent!
        
        # Workflow stores reference to PARENT Invoice
        # When it calls: invoice.on_stage_approved()
        # It calls the PARENT method, NOT the child!
        
        WHY?
        ====
        Because ap_invoice.invoice is an Invoice instance, not an AP_Invoice instance.
        Python's method resolution only looks at the Invoice class hierarchy,
        not at related AP_Invoice.
        
        ap_invoice.invoice.on_stage_approved()  # ← Calls Invoice method
        ap_invoice.on_stage_approved()          # ← Calls AP_Invoice method
        
        But workflow has reference to `invoice` (parent), not `ap_invoice` (child)!
        """
        pass
    
    def test_explain_the_solution(self):
        """
        THE SOLUTION:
        =============
        
        You have THREE options:
        
        OPTION 1: Callback Pattern (RECOMMENDED)
        =========================================
        Parent delegates to child when child exists.
        
        class Invoice(models.Model):
            def on_stage_approved(self, stage):
                # Default parent behavior
                print("Invoice stage approved")
                
                # Delegate to child if exists
                if hasattr(self, 'ap_invoice'):
                    self.ap_invoice.on_ap_stage_approved(stage)
                elif hasattr(self, 'ar_invoice'):
                    self.ar_invoice.on_ar_stage_approved(stage)
        
        class AP_Invoice(models.Model):
            invoice = models.OneToOneField(Invoice, primary_key=True)
            
            def on_ap_stage_approved(self, stage):
                # AP-specific logic here!
                print("AP-specific stage logic")
                self.notify_supplier()
        
        class AR_Invoice(models.Model):
            invoice = models.OneToOneField(Invoice, primary_key=True)
            
            def on_ar_stage_approved(self, stage):
                # AR-specific logic here!
                print("AR-specific stage logic")
                self.notify_customer()
        
        
        OPTION 2: Strategy Pattern with Type Field
        ===========================================
        Store invoice type and use conditional logic.
        
        class Invoice(models.Model):
            invoice_type = models.CharField(choices=[('AP', 'AP'), ('AR', 'AR')])
            
            def on_stage_approved(self, stage):
                if self.invoice_type == 'AP':
                    # AP-specific logic
                    self._handle_ap_stage_approved(stage)
                elif self.invoice_type == 'AR':
                    # AR-specific logic
                    self._handle_ar_stage_approved(stage)
        
        
        OPTION 3: Reverse Lookup Pattern
        ==================================
        Parent uses reverse relation to find and call child method.
        
        class Invoice(models.Model):
            def on_stage_approved(self, stage):
                # Get child instance
                child = self._get_child_invoice()
                
                # Call child-specific method if it exists
                if child and hasattr(child, 'handle_stage_approved'):
                    child.handle_stage_approved(stage)
                else:
                    # Default behavior
                    self._default_stage_approved(stage)
            
            def _get_child_invoice(self):
                \"\"\"Get the child invoice instance (AP or AR).\"\"\"
                if hasattr(self, 'ap_invoice'):
                    return self.ap_invoice
                elif hasattr(self, 'ar_invoice'):
                    return self.ar_invoice
                return None
        
        class AP_Invoice(models.Model):
            invoice = models.OneToOneField(Invoice, primary_key=True)
            
            def handle_stage_approved(self, stage):
                # AP-specific logic
                pass
        """
        pass


class RecommendedPattern(TestCase):
    """
    RECOMMENDED PATTERN: Callback with child-specific hooks
    
    This is the cleanest and most maintainable approach.
    """
    
    def test_recommended_implementation(self):
        """
        IMPLEMENTATION GUIDE:
        ====================
        
        1. Parent (Invoice) implements all required ApprovableInterface methods
        2. Parent calls child-specific hooks when child exists
        3. Each child (AP_Invoice, AR_Invoice) implements its own hooks
        
        CODE STRUCTURE:
        ===============
        
        # In Invoice (parent):
        class Invoice(ApprovableMixin, ApprovableInterface, models.Model):
            
            def on_approval_started(self, workflow_instance):
                # Parent logic
                self.approval_status = 'PENDING_APPROVAL'
                self.save()
                
                # Delegate to child
                self._call_child_hook('on_approval_started_child', workflow_instance)
            
            def on_stage_approved(self, stage_instance):
                # Parent logic
                stage_name = stage_instance.stage_template.name
                print(f"Stage {stage_name} approved")
                
                # Delegate to child
                self._call_child_hook('on_stage_approved_child', stage_instance)
            
            def on_fully_approved(self, workflow_instance):
                # Parent logic
                self.approval_status = 'APPROVED'
                self.approved_at = timezone.now()
                self.save()
                
                # Delegate to child
                self._call_child_hook('on_fully_approved_child', workflow_instance)
            
            def on_rejected(self, workflow_instance, stage_instance=None):
                # Parent logic
                self.approval_status = 'REJECTED'
                self.save()
                
                # Delegate to child
                self._call_child_hook('on_rejected_child', workflow_instance, stage_instance)
            
            def on_cancelled(self, workflow_instance, reason=None):
                # Parent logic
                self.approval_status = 'DRAFT'
                self.save()
                
                # Delegate to child
                self._call_child_hook('on_cancelled_child', workflow_instance, reason)
            
            def _call_child_hook(self, method_name, *args, **kwargs):
                \"\"\"Call child-specific hook method if it exists.\"\"\"
                child = self._get_child()
                if child and hasattr(child, method_name):
                    method = getattr(child, method_name)
                    if callable(method):
                        method(*args, **kwargs)
            
            def _get_child(self):
                \"\"\"Get the child invoice instance.\"\"\"
                if hasattr(self, 'ap_invoice'):
                    return self.ap_invoice
                elif hasattr(self, 'ar_invoice'):
                    return self.ar_invoice
                elif hasattr(self, 'onetimesupplier'):
                    return self.onetimesupplier
                return None
        
        
        # In AP_Invoice (child):
        class AP_Invoice(models.Model):
            invoice = models.OneToOneField(Invoice, primary_key=True)
            supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
            
            # Child-specific hooks (OPTIONAL - implement only if needed)
            
            def on_approval_started_child(self, workflow_instance):
                \"\"\"AP-specific logic when approval starts.\"\"\"
                # Send email to supplier
                self.notify_supplier_submission()
            
            def on_stage_approved_child(self, stage_instance):
                \"\"\"AP-specific logic when a stage is approved.\"\"\"
                stage_name = stage_instance.stage_template.name
                
                # Different actions based on stage
                if stage_name == 'Accountant Review':
                    self.mark_documents_verified()
                elif stage_name == 'Finance Manager Review':
                    self.prepare_for_payment()
            
            def on_fully_approved_child(self, workflow_instance):
                \"\"\"AP-specific logic when fully approved.\"\"\"
                # Schedule payment
                self.schedule_payment()
                
                # Notify supplier
                self.notify_supplier_approval()
                
                # Update purchase order if linked
                if hasattr(self, 'purchase_order'):
                    self.purchase_order.mark_invoice_approved()
            
            def on_rejected_child(self, workflow_instance, stage_instance=None):
                \"\"\"AP-specific logic when rejected.\"\"\"
                # Notify supplier
                self.notify_supplier_rejection()
            
            # Helper methods
            def notify_supplier_submission(self):
                # Email logic
                pass
            
            def mark_documents_verified(self):
                # Update internal flags
                pass
            
            def schedule_payment(self):
                # Create payment record
                pass
        
        
        # In AR_Invoice (child):
        class AR_Invoice(models.Model):
            invoice = models.OneToOneField(Invoice, primary_key=True)
            customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
            
            # AR-specific hooks (different from AP!)
            
            def on_fully_approved_child(self, workflow_instance):
                \"\"\"AR-specific logic when fully approved.\"\"\"
                # Send invoice to customer
                self.send_to_customer()
                
                # Record in accounting
                self.record_receivable()
            
            def send_to_customer(self):
                # Email invoice to customer
                pass
        
        
        BENEFITS:
        =========
        ✓ Parent implements required interface (ApprovalManager works)
        ✓ Each child can have custom logic (optional)
        ✓ Children don't need to implement all hooks (only what they need)
        ✓ Easy to add new children without modifying parent
        ✓ Clear separation of concerns
        ✓ No code duplication
        """
        pass


class AlternativePatterns(TestCase):
    """
    Alternative patterns if you want different approaches.
    """
    
    def test_alternative_with_signals(self):
        """
        ALTERNATIVE: Django Signals Pattern
        ====================================
        
        Use signals to allow children to react to parent events.
        
        # In Invoice (parent):
        from django.dispatch import Signal
        
        invoice_stage_approved = Signal()  # Custom signal
        
        class Invoice(models.Model):
            def on_stage_approved(self, stage_instance):
                # Parent logic
                print("Stage approved")
                
                # Send signal
                invoice_stage_approved.send(
                    sender=self.__class__,
                    invoice=self,
                    stage_instance=stage_instance
                )
        
        
        # In AP_Invoice (child):
        from django.dispatch import receiver
        from .parent_model import invoice_stage_approved
        
        @receiver(invoice_stage_approved)
        def handle_ap_stage_approved(sender, invoice, stage_instance, **kwargs):
            # Check if this is an AP invoice
            if hasattr(invoice, 'ap_invoice'):
                ap_invoice = invoice.ap_invoice
                # AP-specific logic
                ap_invoice.notify_supplier()
        
        
        PROS:
        - Decoupled (child doesn't need to be called by parent)
        - Multiple receivers can listen to same event
        
        CONS:
        - Harder to debug (signal receivers hidden)
        - Performance overhead
        - Less explicit than callback pattern
        """
        pass
    
    def test_alternative_with_registry(self):
        """
        ALTERNATIVE: Handler Registry Pattern
        ======================================
        
        Register handlers for different invoice types.
        
        # Registry
        class InvoiceApprovalHandlers:
            _handlers = {}
            
            @classmethod
            def register(cls, invoice_type, handler):
                cls._handlers[invoice_type] = handler
            
            @classmethod
            def get_handler(cls, invoice_type):
                return cls._handlers.get(invoice_type)
        
        
        # In Invoice (parent):
        class Invoice(models.Model):
            invoice_type = models.CharField(max_length=10)
            
            def on_stage_approved(self, stage_instance):
                # Get handler for this type
                handler = InvoiceApprovalHandlers.get_handler(self.invoice_type)
                
                if handler:
                    handler.handle_stage_approved(self, stage_instance)
                else:
                    # Default behavior
                    print("Default stage approved")
        
        
        # AP Handler
        class APInvoiceApprovalHandler:
            @staticmethod
            def handle_stage_approved(invoice, stage_instance):
                ap_invoice = invoice.ap_invoice
                # AP-specific logic
                ap_invoice.notify_supplier()
        
        # Register
        InvoiceApprovalHandlers.register('AP', APInvoiceApprovalHandler)
        
        
        PROS:
        - Flexible and extensible
        - Can swap handlers easily
        
        CONS:
        - More complex setup
        - Requires invoice_type field
        """
        pass


# Summary recommendation in plain text
"""
FINAL RECOMMENDATION FOR YOUR INVOICE SYSTEM:
==============================================

Use the CALLBACK PATTERN (Option 1 from test_recommended_implementation):

STEP 1: Update Invoice (parent)
================================
Add these methods to Invoice class:

def _call_child_hook(self, method_name, *args, **kwargs):
    child = self._get_child()
    if child and hasattr(child, method_name):
        method = getattr(child, method_name)
        if callable(method):
            method(*args, **kwargs)

def _get_child(self):
    if hasattr(self, 'ap_invoice'):
        return self.ap_invoice
    elif hasattr(self, 'ar_invoice'):
        return self.ar_invoice
    elif hasattr(self, 'onetimesupplier'):
        return self.onetimesupplier
    return None

# In each ApprovableInterface method, add at the end:
def on_stage_approved(self, stage_instance):
    # Parent logic here
    stage_name = stage_instance.stage_template.name
    print(f"Stage {stage_name} approved")
    
    # Delegate to child (ADD THIS LINE)
    self._call_child_hook('on_stage_approved_child', stage_instance)


STEP 2: In AP_Invoice (child)
==============================
Add OPTIONAL child-specific methods:

def on_stage_approved_child(self, stage_instance):
    # Your AP-specific logic!
    if stage_instance.stage_template.name == 'Accountant Review':
        self.notify_supplier("Documents verified")
    elif stage_instance.stage_template.name == 'CFO Approval':
        self.schedule_payment()

def on_fully_approved_child(self, workflow_instance):
    # Your AP-specific logic when fully approved!
    self.send_to_payment_system()
    self.notify_supplier("Invoice approved for payment")


STEP 3: In AR_Invoice (child)
==============================
Different child-specific methods for AR!

def on_fully_approved_child(self, workflow_instance):
    # Your AR-specific logic!
    self.send_invoice_to_customer()
    self.record_receivable()


WHY THIS IS BEST:
=================
✓ Parent satisfies ApprovalManager requirements (implements ApprovableInterface)
✓ Each child can customize behavior (optional, implement only what you need)
✓ No duplication (parent handles common logic)
✓ Clear and explicit (easy to understand and debug)
✓ Extensible (easy to add new invoice types)
✓ Maintains your existing parent-child architecture

WHAT YOU CAN DO:
================
1. Override individual stages (on_stage_approved_child)
2. Override final approval (on_fully_approved_child)
3. Add custom notifications per invoice type
4. Execute different business logic per invoice type
5. All while keeping parent interface intact!
"""
