# apps/shared/tenants/services.py
from django.contrib.auth import get_user_model
User = get_user_model()


class TenantLimitService:
    """
    Service class to handle tenant limits based on subscription plan
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
        self._load_limits()
    
    def _load_limits(self):
        """Load limits from the tenant's subscription plan"""
        # Default limits (when no plan is assigned)
        self.user_limit = 5
        self.product_limit = 100
        self.branch_limit = 1
        self.storage_limit = 1
        
        # ✅ Try to get limits from subscription plan
        try:
            from apps.shared.tenants.models import SubscriptionPlan
            
            if self.tenant.subscription_plan:
                plan = SubscriptionPlan.objects.get(code=self.tenant.subscription_plan)
                self.user_limit = getattr(plan, 'max_users', 5)
                self.product_limit = getattr(plan, 'max_products', 100)
                self.branch_limit = getattr(plan, 'max_branches', 1)
                self.storage_limit = getattr(plan, 'max_storage_gb', 1)
                print(f"✅ Loaded plan: {plan.code} - Storage: {self.storage_limit} GB")
            else:
                print(f"⚠️ No subscription plan for tenant: {self.tenant.company_name}")
                # ✅ Try to get from tenant's subscription_plan field
                if hasattr(self.tenant, 'subscription_plan') and self.tenant.subscription_plan:
                    plan = SubscriptionPlan.objects.get(code=self.tenant.subscription_plan)
                    self.storage_limit = getattr(plan, 'max_storage_gb', 1)
                    print(f"✅ Loaded from tenant field: {self.storage_limit} GB")
        except SubscriptionPlan.DoesNotExist:
            print(f"❌ Plan not found: {self.tenant.subscription_plan}")
        except Exception as e:
            print(f"❌ Error loading plan: {e}")
    
    def has_limits(self):
        """Check if tenant has any limits configured"""
        return True
    
    # ============================================
    # USER LIMITS
    # ============================================
    def get_user_limit(self):
        return self.user_limit
    
    def get_user_count(self):
        return User.objects.filter(tenant=self.tenant, is_active=True).count()
    
    def get_user_remaining(self):
        remaining = self.user_limit - self.get_user_count()
        return max(0, remaining)
    
    def get_user_percentage(self):
        if not self.user_limit or self.user_limit == 0:
            return 0
        count = self.get_user_count()
        return min(100, (count / self.user_limit) * 100)
    
    def is_user_limit_reached(self):
        if not self.user_limit:
            return False
        return self.get_user_count() >= self.user_limit
    
    # ============================================
    # PRODUCT LIMITS
    # ============================================
    def get_product_limit(self):
        return self.product_limit
    
    def get_product_count(self):
        from apps.tech_master.inventory.models import Product
        return Product.objects.filter(
            tenant=self.tenant,
            is_active=True,
            is_discontinued=False
        ).count()
    
    def get_product_remaining(self):
        remaining = self.product_limit - self.get_product_count()
        return max(0, remaining)
    
    def get_product_percentage(self):
        if not self.product_limit or self.product_limit == 0:
            return 0
        count = self.get_product_count()
        return min(100, (count / self.product_limit) * 100)
    
    def is_product_limit_reached(self):
        if not self.product_limit:
            return False
        return self.get_product_count() >= self.product_limit
    
    # ============================================
    # BRANCH LIMITS
    # ============================================
    def get_branch_limit(self):
        return self.branch_limit
    
    def get_branch_count(self):
        from apps.tech_master.inventory.models import Branch
        return Branch.objects.filter(
            tenant=self.tenant,
            is_active=True
        ).count()
    
    def get_branch_remaining(self):
        remaining = self.branch_limit - self.get_branch_count()
        return max(0, remaining)
    
    def get_branch_percentage(self):
        if not self.branch_limit or self.branch_limit == 0:
            return 0
        count = self.get_branch_count()
        return min(100, (count / self.branch_limit) * 100)
    
    def is_branch_limit_reached(self):
        if not self.branch_limit:
            return False
        return self.get_branch_count() >= self.branch_limit
    
    # ============================================
    # STORAGE LIMITS
    # ============================================
    def get_storage_limit(self):
        """Get storage limit in GB from subscription plan"""
        return self.storage_limit
    
    def get_storage_used(self):
        """Calculate storage used in GB"""
        total_bytes = 0
        
        try:
            from apps.tech_master.inventory.models import Product
            from apps.tech_master.expenses.models import Expense
            
            # 1. Product Images
            products = Product.objects.filter(tenant=self.tenant)
            for product in products:
                if product.image:
                    try:
                        if hasattr(product.image, 'size'):
                            total_bytes += product.image.size
                    except:
                        pass
            
            # 2. Tenant Logo
            if self.tenant.logo:
                try:
                    if hasattr(self.tenant.logo, 'size'):
                        total_bytes += self.tenant.logo.size
                except:
                    pass
            
            # 3. Expense Receipts
            expenses = Expense.objects.filter(tenant=self.tenant)
            for expense in expenses:
                if expense.receipt:
                    try:
                        if hasattr(expense.receipt, 'size'):
                            total_bytes += expense.receipt.size
                    except:
                        pass
                    
        except Exception as e:
            print(f"Error calculating storage: {e}")
        
        # Convert bytes to GB (1 GB = 1,073,741,824 bytes)
        if total_bytes == 0:
            return 0
        gb = total_bytes / (1024 * 1024 * 1024)
        return round(gb, 2)
    
    def get_storage_remaining(self):
        remaining = self.storage_limit - self.get_storage_used()
        return max(0, remaining)
    
    def get_storage_percentage(self):
        if not self.storage_limit or self.storage_limit == 0:
            return 0
        used = self.get_storage_used()
        return min(100, (used / self.storage_limit) * 100)
    
    def is_storage_limit_reached(self):
        if not self.storage_limit:
            return False
        return self.get_storage_used() >= self.storage_limit