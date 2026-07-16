# ============================================
# CONFIG SETTINGS - PYTHONANYWHERE READY (FULLY FIXED)
# ============================================
from pathlib import Path
import os
import sys
from dotenv import load_dotenv
import dj_database_url
from typing import Dict, Any

# ============================================
# BASE DIRECTORY
# ============================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# ENVIRONMENT DETECTION
# ============================================
# Detect if running on PythonAnywhere
IS_PYTHONANYWHERE = 'pythonanywhere' in sys.executable or os.getenv('PYTHONANYWHERE_DOMAIN') is not None

# ============================================
# ENVIRONMENT LOADING - FORCE FOR PYTHONANYWHERE
# ============================================

# ✅ If on PythonAnywhere, ALWAYS use .env.production
if IS_PYTHONANYWHERE:
    env_file = BASE_DIR / '.env.production'
    print(f"🏠 PythonAnywhere detected - loading {env_file}")
else:
    ENV = os.getenv('DJANGO_ENV', 'development')
    if ENV == 'production':
        env_file = BASE_DIR / '.env.production'
    elif ENV == 'test':
        env_file = BASE_DIR / '.env.test'
    else:
        env_file = BASE_DIR / '.env'

if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✅ Loaded: {env_file}")
else:
    print(f"❌ File not found: {env_file}")
    # Create default .env.production on PythonAnywhere
    if IS_PYTHONANYWHERE:
        with open(env_file, 'w') as f:
            f.write("MYSQL_DATABASE=RONOSYSTEMS$RSMASTER\n")
            f.write("MYSQL_USER=RONOSYSTEMS\n")
            f.write("MYSQL_PASSWORD=Kiprono@1997\n")
            f.write("MYSQL_HOST=RONOSYSTEMS.mysql.pythonanywhere-services.com\n")
            f.write("DJANGO_ENV=production\n")
            f.write("DEBUG=False\n")
            f.write("SECRET_KEY=gh5-3pz5go7hlm0)yfmdjw8f5l)%@b+*e*a-2xw(^3^g-un&zm\n")
            f.write("ALLOWED_HOSTS=RONOSYSTEMS.pythonanywhere.com\n")
            f.write("OFFLINE_MODE=False\n")
            f.write("TIME_ZONE=Africa/Nairobi\n")
            f.write("CORS_ALLOWED_ORIGINS=https://RONOSYSTEMS.pythonanywhere.com\n")
            f.write("CSRF_TRUSTED_ORIGINS=https://RONOSYSTEMS.pythonanywhere.com\n")
        load_dotenv(env_file, override=True)
        print("✅ Created default .env.production")


# ✅ Define ENV after loading (for both environments)
ENV = os.getenv('DJANGO_ENV', 'development')

# ✅ Now set OFFLINE_MODE AFTER loading .env
OFFLINE_MODE = os.getenv('OFFLINE_MODE', 'False') == 'True'

# ============================================
# CORE SETTINGS
# ============================================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-your-secret-key-here')
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# --- ALLOWED HOSTS (Fixed for PythonAnywhere) ---
if IS_PYTHONANYWHERE:
    # Allow all PythonAnywhere subdomains + custom domains
    ALLOWED_HOSTS = [
        '.pythonanywhere.com',  # Wildcard for yourusername.pythonanywhere.com
        os.getenv('ALLOWED_HOSTS', ''),
    ]
else:
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Clean up empty entries
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS if host.strip()]

# ============================================
# AUTHENTICATION
# ============================================
AUTH_USER_MODEL = 'users.User'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# ============================================
# PROJECT TYPES (UPDATED: TRONIC_MASTER)
# ============================================
PROJECT_TYPES = {
    'TRONIC_MASTER': {
        'name': 'TRONIC MASTER',
        'code': 'TRONIC_MASTER',
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
        'active': True,
        'description': 'Hotel & Booking Management'
    },
    'FOOD_MASTER': {
        'name': 'FOOD MASTER',
        'code': 'FOOD_MASTER',
        'icon': 'fa-utensils',
        'color': '#198754',
        'active': True,
        'description': 'Restaurant & Kitchen Management'
    },
    'RETAIL_MASTER': {
        'name': 'RETAIL MASTER',
        'code': 'RETAIL_MASTER',
        'icon': 'fa-store',
        'color': '#6f42c1',
        'active': True,
        'description': 'General Retail Management'
    },
    'HEALTH_MASTER': {
        'name': 'HEALTH MASTER',
        'code': 'HEALTH_MASTER',
        'icon': 'fa-heartbeat',
        'color': '#dc3545',
        'active': True,
        'description': 'Pharmacy & Health Management'
    },
    'FASHION_MASTER': {
        'name': 'FASHION MASTER',
        'code': 'FASHION_MASTER',
        'icon': 'fa-tshirt',
        'color': '#e83e8c',
        'active': True,
        'description': 'Fashion & Clothing Management'
    },
    'RENTAL_MASTER': {
        'name': 'RENTAL MASTER',
        'code': 'RENTAL_MASTER',
        'icon': 'fa-rental',
        'color': "#ffee00",
        'active': True,
        'description': 'Rental & Apartments Management'
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
    'django.contrib.humanize',

    # Third party apps
    'corsheaders',
    'rest_framework',
    'whitenoise.runserver_nostatic',

    # Shared apps
    'apps.shared',
    'apps.shared.roles',
    'apps.shared.tenants',
    'apps.shared.users',
    'apps.shared.customers',
    'apps.shared.notifications',
    'apps.shared.payments',
    'apps.shared.audit_log',
    'apps.shared.portal',
    'apps.shared.permissions',
    'apps.shared.settings',
    'apps.shared.powersync',
    'apps.shared.chats',
    'apps.shared.expenses',
    'apps.shared.reports',

    # TRONIC Master apps (renamed from tech_master)
    'apps.tronic_master',

    # Hotel_master apps
    'apps.hotel_master',

    # Rental master apps
    'apps.rental_master',

    'apps.food_master',
    'apps.retail_master',
    'apps.health_master',
    'apps.fashion_master',
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

    # ✅ Keep ONLY ONE TenantMiddleware
    'apps.shared.tenants.middleware.TenantMiddleware', 
    
    # Your other custom middleware
    'apps.shared.middleware.OfflineSyncMiddleware',
    'apps.shared.portal.middleware.ProjectTypeMiddleware',
    'apps.shared.portal.middleware.MaintenanceModeMiddleware',
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
                'django.template.context_processors.media',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # Your custom context processors
                'apps.shared.context_processors.tenant_logo_context',
                'apps.shared.context_processors.offline_mode',
                'apps.shared.context_processors.tenant_settings',

                # Other existing ones from your config
                'apps.shared.portal.context_processors.user_role',
                'apps.shared.portal.context_processors.tenant_context',
                'apps.shared.portal.context_processors.user_role_context',
                'apps.shared.portal.context_processors.project_context',
                'apps.shared.settings.context_processors.company_settings',
                'apps.shared.portal.context_processors.permissions_context',
                'apps.food_master.context_processors.user_permissions',
            ],
        },
    },
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

WSGI_APPLICATION = 'config.wsgi.application'

# ============================================
# DATABASE CONFIGURATION - PYTHONANYWHERE READY
# ============================================

def get_database_config(offline_mode=False) -> Dict[str, Any]:
    """
    Returns database configuration based on environment variables.
    Automatically switches to SQLite when offline.
    """

    # --- PRIORITY 1: PYTHONANYWHERE MySQL (Auto-detected) ---
    if IS_PYTHONANYWHERE:
        print("🏠 Running on PythonAnywhere - Configuring MySQL")

        # Get MySQL credentials from environment
        db_name = os.getenv('MYSQL_DATABASE')
        db_user = os.getenv('MYSQL_USER')
        db_password = os.getenv('MYSQL_PASSWORD')
        db_host = os.getenv('MYSQL_HOST', 'mysql.pythonanywhere-services.com')

        # ✅ DEBUG: Print what we found
        print(f"   🔍 MYSQL_DATABASE: {db_name}")
        print(f"   🔍 MYSQL_USER: {db_user}")
        print(f"   🔍 MYSQL_PASSWORD: {'✅ SET' if db_password else '❌ NOT SET'}")
        print(f"   🔍 MYSQL_HOST: {db_host}")

        # Validate credentials exist
        if not all([db_name, db_user, db_password]):
            raise ValueError(
                f"❌ MySQL credentials not set! "
                f"MYSQL_DATABASE={db_name}, MYSQL_USER={db_user}, "
                f"MYSQL_PASSWORD={'SET' if db_password else 'NOT SET'}"
            )

        return {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': db_name,
                'USER': db_user,
                'PASSWORD': db_password,
                'HOST': db_host,
                'PORT': '3306',
                'OPTIONS': {
                    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                    'charset': 'utf8mb4',
                },
                'CONN_MAX_AGE': 600,
                'CONN_HEALTH_CHECKS': True,
            }
        }

    # --- PRIORITY 2: OFFLINE MODE (SQLite) ---
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

    # --- PRIORITY 3: DATABASE_URL (For Heroku/Other cloud) ---
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        config = dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True
        )
        return {'default': dict(config)}

    # --- PRIORITY 4: Individual PostgreSQL Settings ---
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

    # --- PRIORITY 5: Default SQLite (Local development) ---
    else:
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
# DATABASES - FINAL ASSIGNMENT
# ============================================
DATABASES = get_database_config(offline_mode=OFFLINE_MODE)

# Print which database we're using (for debugging)
db_engine = DATABASES['default'].get('ENGINE', 'unknown')
if 'sqlite3' in db_engine:
    print(f"🗄️  Using SQLite: {DATABASES['default'].get('NAME', '')}")
else:
    print(f"🗄️  Using {db_engine}")

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
# STATIC & MEDIA FILES - PYTHONANYWHERE OPTIMIZED
# ============================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Different paths for PythonAnywhere (absolute paths required)
if IS_PYTHONANYWHERE:
    PA_USERNAME = os.getenv('PYTHONANYWHERE_USERNAME', 'RONOSYSTEMS')
    STATIC_ROOT = f'/home/{PA_USERNAME}/staticfiles'
    MEDIA_ROOT = f'/home/{PA_USERNAME}/media'
else:
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    MEDIA_ROOT = BASE_DIR / 'media'

# Ensure directories exist (creates them if not)
os.makedirs(STATIC_ROOT, exist_ok=True)
os.makedirs(MEDIA_ROOT, exist_ok=True)

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'

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
# CORS SETTINGS - PYTHONANYWHERE READY
# ============================================
if IS_PYTHONANYWHERE:
    PA_DOMAIN = os.getenv('PYTHONANYWHERE_DOMAIN', 'RONOSYSTEMS.pythonanywhere.com')
    CORS_ALLOWED_ORIGINS = [
        f'https://{PA_DOMAIN}',
        f'http://{PA_DOMAIN}',
        'https://*.pythonanywhere.com',
    ]
else:
    CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS if origin.strip()]

# ============================================
# SECURITY SETTINGS - PYTHONANYWHERE OPTIMIZED
# ============================================

# ✅ Define default values (prevents "unbound" errors)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
CSRF_TRUSTED_ORIGINS = []

if not DEBUG:
    # PythonAnywhere handles SSL termination, so we don't redirect
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Optional HSTS (PythonAnywhere may already handle this)
    # SECURE_HSTS_SECONDS = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True

    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # CSRF Trusted Origins for PythonAnywhere
    if IS_PYTHONANYWHERE:
        PA_DOMAIN = os.getenv('PYTHONANYWHERE_DOMAIN', 'RONOSYSTEMS.pythonanywhere.com')
        CSRF_TRUSTED_ORIGINS = [
            f'https://{PA_DOMAIN}',
            f'http://{PA_DOMAIN}',
            'https://*.pythonanywhere.com',
        ]

    # Add any custom origins from environment
    csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
    if csrf_origins:
        CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in csrf_origins.split(',') if origin.strip()])

    # Clean up empty entries
    CSRF_TRUSTED_ORIGINS = [origin for origin in CSRF_TRUSTED_ORIGINS if origin]

# ============================================
# LOGGING - CLEAN VERSION (Only INFO and above)
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'INFO',  # Only show INFO and above
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'logs' / 'django.log'),
            'formatter': 'verbose',
            'level': 'INFO',  # Only show INFO and above in file
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        # Django core loggers - INFO and above only
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',  # Only show database errors
            'propagate': False,
        },
        'django.template': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',  # Only show template errors
            'propagate': False,
        },
        'django.utils.autoreload': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',  # Only show warnings and above
            'propagate': False,
        },

        # Suppress context processors debug messages
        'apps.shared.portal.context_processors': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',  # Suppress "Company name loaded" messages
            'propagate': False,
        },

        # App loggers - INFO and above
        'apps.shared.sync': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.shared.middleware': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.shared.chats': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.tronic_master': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.fashion_master': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.hotel_master': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.food_master': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },

        # Suppress template loader debug messages
        'django.template.loaders': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.template.backends.django': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
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
print(f"🔧 Environment: {ENV if not IS_PYTHONANYWHERE else 'production (PythonAnywhere)'}")
print(f"🏠 PythonAnywhere: {IS_PYTHONANYWHERE}")
print(f"🗄️  Database Engine: {DATABASES['default'].get('ENGINE', 'unknown')}")
print(f"📴 Offline Mode: {OFFLINE_MODE}")
print(f"🌐 Allowed Hosts: {ALLOWED_HOSTS}")
if not DEBUG:
    print(f"🔐 SECURE_SSL_REDIRECT: {SECURE_SSL_REDIRECT}")