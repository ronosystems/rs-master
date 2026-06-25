# ============================================
# CONFIG SETTINGS
# ============================================
from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent

# Force OFFLINE_MODE from environment variable
OFFLINE_MODE = os.getenv('OFFLINE_MODE', 'False') == 'True'

# ============================================
# ENVIRONMENT LOADING
# ============================================
ENV = os.getenv('DJANGO_ENV', 'development')

if ENV == 'production':
    env_file = BASE_DIR / '.env.production'
elif ENV == 'test':
    env_file = BASE_DIR / '.env.test'
else:
    env_file = BASE_DIR / '.env'

if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv(BASE_DIR / '.env')

# ============================================
# CORE SETTINGS
# ============================================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-your-secret-key-here')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# ============================================
# AUTHENTICATION
# ============================================
AUTH_USER_MODEL = 'users.User'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ============================================
# PROJECT TYPES
# ============================================
PROJECT_TYPES = {
    'TECH_MASTER': {
        'name': 'TECH MASTER',
        'code': 'TECH_MASTER',
        'icon': 'fa-microchip',
        'color': '#0d6efd',
        'active': True,
        'description': 'POS & Inventory for Electronics'
    },
    'HOTEL_MASTER': {
        'name': 'HOTEL MASTER',
        'code': 'HOTEL_MASTER',
        'icon': 'fa-hotel',
        'color': '#fd7e14',
        'active': False,
        'description': 'Hotel & Booking Management'
    },
    'FOOD_MASTER': {
        'name': 'FOOD MASTER',
        'code': 'FOOD_MASTER',
        'icon': 'fa-utensils',
        'color': '#198754',
        'active': False,
        'description': 'Restaurant & Kitchen Management'
    },
    'RETAIL_MASTER': {
        'name': 'RETAIL MASTER',
        'code': 'RETAIL_MASTER',
        'icon': 'fa-store',
        'color': '#6f42c1',
        'active': False,
        'description': 'General Retail Management'
    },
    'HEALTH_MASTER': {
        'name': 'HEALTH MASTER',
        'code': 'HEALTH_MASTER',
        'icon': 'fa-heartbeat',
        'color': '#dc3545',
        'active': False,
        'description': 'Pharmacy & Health Management'
    },
    'FASHION_MASTER': {
        'name': 'FASHION MASTER',
        'code': 'FASHION_MASTER',
        'icon': 'fa-tshirt',
        'color': '#e83e8c',
        'active': False,
        'description': 'Fashion & Clothing Management'
    }
}

# ============================================
# INSTALLED APPS
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions', 
    
    # Third party apps
    'corsheaders',
    'rest_framework',
    'whitenoise.runserver_nostatic',
    
    # Shared apps
    'apps.shared',
    'apps.shared.tenants',
    'apps.shared.users',
    'apps.shared.customers',
    'apps.shared.notifications', 
    'apps.shared.payments',
    'apps.shared.audit_log', 
    'apps.shared.portal',
    'apps.shared.settings',
    'apps.shared.powersync',

    # Project apps
    'apps.tech_master.inventory',
    'apps.tech_master.sales',
    'apps.tech_master.cashier',
    'apps.tech_master.expenses',
    'apps.tech_master.reports',
]

# ============================================
# MIDDLEWARE
# ============================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.shared.portal.middleware.MaintenanceModeMiddleware',
    'apps.shared.middleware.offline_sync.OfflineSyncMiddleware',
]

ROOT_URLCONF = 'config.urls'

# ============================================
# TEMPLATES
# ============================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.shared.portal.context_processors.user_role',
                'apps.shared.portal.context_processors.tenant_context',
                'apps.shared.portal.context_processors.user_role_context',
                'apps.shared.context_processors.tenant_logo_context',
                'apps.shared.context_processors.offline_mode', 
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ============================================
# OFFLINE DATABASE HANDLING
# ============================================

def is_database_available():
    """Check if the database host is reachable"""
    import socket
    import os
    import urllib.parse
    
    database_url = os.getenv('DATABASE_URL', '')
    
    if not database_url:
        print("📶 No DATABASE_URL set - using SQLite")
        return True  # SQLite is always available
    
    try:
        parsed = urllib.parse.urlparse(database_url)
        host = parsed.hostname
        
        if not host:
            return True
        
        socket.setdefaulttimeout(3)
        ip = socket.gethostbyname(host)
        print(f"✅ Database host resolved: {host} -> {ip}")
        return True
        
    except socket.gaierror as e:
        print(f"❌ Database host unreachable: {e}")
        return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False
    finally:
        socket.setdefaulttimeout(None)

# ✅ Check environment variable first, then fallback to database check
# If OFFLINE_MODE is explicitly set in environment, use that
env_offline = os.getenv('OFFLINE_MODE', '').lower()
if env_offline in ['true', '1', 'yes']:
    OFFLINE_MODE = True
    print("📴 OFFLINE MODE FORCED BY ENVIRONMENT VARIABLE")
else:
    # Otherwise auto-detect
    OFFLINE_MODE = not is_database_available()

if OFFLINE_MODE:
    print("📴 OFFLINE MODE ACTIVATED - Using local cache")
else:
    print("📶 ONLINE MODE - Using PostgreSQL database")




# ============================================
# DATABASE CONFIGURATION
# ============================================
def get_database_config(offline_mode=False) -> Dict[str, Any]:
    """
    Returns database configuration based on environment variables.
    Automatically switches to SQLite when offline.
    """
    
    # Check if we're offline
    if offline_mode:
        print("📴 OFFLINE: Using SQLite cache database")
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': str(BASE_DIR / 'offline_cache.db'),
                'OPTIONS': {
                    'timeout': 20,
                },
            }
        }
    
    # Check if DATABASE_URL is provided (production)
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        config = dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True
        )
        return {'default': dict(config)}
    
    # Otherwise build from individual settings
    engine = os.getenv('DATABASE_ENGINE', 'django.db.backends.sqlite3')
    
    if engine == 'django.db.backends.postgresql':
        return {
            'default': {
                'ENGINE': engine,
                'NAME': os.getenv('PGDATABASE', ''),
                'USER': os.getenv('PGUSER', ''),
                'PASSWORD': os.getenv('PGPASSWORD', ''),
                'HOST': os.getenv('PGHOST', 'localhost'),
                'PORT': os.getenv('PGPORT', '5432'),
                'OPTIONS': {
                    'sslmode': os.getenv('PGSSLMODE', 'require'),
                    'connect_timeout': 10,
                },
                'CONN_MAX_AGE': int(os.getenv('CONN_MAX_AGE', '600')),
                'CONN_HEALTH_CHECKS': True,
                'ATOMIC_REQUESTS': True,
            }
        }
    else:
        # SQLite configuration
        db_name = os.getenv('DATABASE_NAME', 'db.sqlite3')
        
        if ENV == 'test':
            db_name = ':memory:'
        
        if db_name == ':memory:':
            return {
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            }
        else:
            return {
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': str(BASE_DIR / db_name),
                }
            }

# ============================================
# DATABASES
# ============================================
# Now assign the databases - pass OFFLINE_MODE
DATABASES = get_database_config(offline_mode=OFFLINE_MODE)

# Print which database we're using
if DEBUG:
    db_engine = DATABASES['default'].get('ENGINE', 'unknown')
    if 'sqlite3' in db_engine:
        print(f"🗄️  Using SQLite: {DATABASES['default'].get('NAME', '')}")
    else:
        print(f"🗄️  Using PostgreSQL")




# ============================================
# AUTH PASSWORD VALIDATORS
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ============================================
# INTERNATIONALIZATION
# ============================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'Africa/Nairobi')
USE_I18N = True
USE_TZ = True

# ============================================
# STATIC & MEDIA FILES
# ============================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ============================================
# DEFAULT FIELD
# ============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# NEON AUTH & POWERSYNC SETTINGS
# ============================================
NEON_AUTH_URL = os.getenv('NEON_AUTH_URL', '')
POWERSYNC_URL = os.getenv('POWERSYNC_URL', 'https://6a38344d0ef84ed671a39215.powersync.journeyapps.com')
POWERSYNC_API_KEY = os.getenv('POWERSYNC_API_KEY', '')

# ============================================
# CORS SETTINGS
# ============================================
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [origin for origin in CORS_ALLOWED_ORIGINS if origin]

# ============================================
# SECURITY SETTINGS (Production only)
# ============================================
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True') == 'True'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True') == 'True'
    CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True') == 'True'
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    
    csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins.split(',') if origin.strip()]

# ============================================
# LOGGING
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose' if DEBUG else 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'logs' / 'django.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.shared.sync': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
if not LOGS_DIR.exists():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================
# REST FRAMEWORK SETTINGS
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ============================================
# ENVIRONMENT INFO (for debugging)
# ============================================
if DEBUG:
    print(f"🔧 Environment: {ENV}")
    print(f"🗄️  Database: {DATABASES['default'].get('ENGINE', 'unknown')}")
    print(f"📴 Offline Mode: {OFFLINE_MODE}")
    if ENV == 'production':
        print(f"🌐 Neon Auth: {NEON_AUTH_URL}")
        print(f"🔄 PowerSync: {POWERSYNC_URL}")